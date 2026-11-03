import inspect

import numpy as np
import pandas as pd
import pytest
import xarray as xr

import watch_duck.summary.main as summary_main
from watch_duck.common.wdir import WorkingDirectory
from watch_duck.summary.main import get_summary, show_summary

# hourly steps 0..240, so that there are 241 times and 240 hours (differences)
N = 241
COMPLETE, QUEUED, ACTIVE, ABORTED, SUSPENDED = 0, 1, 2, 3, 4
DELTA_T = '48h'


def make_ds(index, state, n_total=None):
    index = np.asarray(index, dtype=int)
    state = np.asarray(state, dtype=int)
    assert len(index) == N
    assert len(state) == N
    time = pd.date_range('2020-02-01', periods=N, freq='1h')
    date_start = pd.Timestamp('2020-01-01')
    if n_total is None:
        # one year with a 6-hourly frequency: total = 1465
        date_end = pd.Timestamp('2021-01-01')
    else:
        date_end = date_start + pd.Timedelta('6h') * (n_total - 1)
    return xr.Dataset(
        {
            'index': (('exp', 'time'), index[None, :]),
            'state': (('exp', 'time'), state[None, :]),
            'date_start': ('exp', np.array([date_start], dtype='datetime64[ns]')),
            'date_end': ('exp', np.array([date_end], dtype='datetime64[ns]')),
            'date_freq': ('exp', np.array([6])),
        },
        coords={'exp': ['a'], 'time': time},
    )


def speed(ds, **kwargs):
    options = {'exclude_aborted': False, 'exclude_suspended': False} | kwargs
    return float(get_summary(ds, DELTA_T, **options).speed_it_day.item())


def hours():
    return np.arange(N)


def all_active():
    return np.full(N, ACTIVE)


# each case returns (index, state, n_total)


def case_steady():
    return hours(), all_active(), None


def case_restart_mid_run():
    # 2 it/h until hour 219, then back to 0 at hour 220 and 1 it/h
    t = hours()
    return np.where(t <= 219, 2 * t, t - 220), all_active(), None


def case_restart_across_missing_hours():
    # hours 201..205 are missing (state -1, index -1)
    t = hours()
    index = np.where(t <= 200, 2 * t, t - 206)
    state = all_active()
    index[201:206] = -1
    state[201:206] = -1
    return index, state, None


def case_complete_then_restart():
    # complete for days (hours 101..200), then restart from scratch at 3 it/h
    t = hours()
    index = np.where(t <= 100, t, 100)
    index = np.where(t >= 201, 3 * (t - 201), index)
    state = all_active()
    state[101:201] = COMPLETE
    return index, state, None


def case_complete_then_extended():
    # complete (hours 101..200), then extended without a drop at 2 it/h
    # window: 39 hours at 2 it/h (201..239) + 8 older increments at 1 it/h
    # (92..100) -> (39 * 2 + 8) / 48 * 24 = 43
    t = hours()
    index = np.where(t <= 100, t, 100)
    index = np.where(t >= 201, 100 + 2 * (t - 200), index)
    state = all_active()
    state[101:201] = COMPLETE
    return index, state, None


def case_aborted_suspended():
    # 1 it/h, flat during suspended (200..209) and aborted (220..229)
    increment = np.ones(N)
    state = all_active()
    state[200:210] = SUSPENDED
    state[220:230] = ABORTED
    increment[200:210] = 0
    increment[220:230] = 0
    index = np.concatenate([[0], np.cumsum(increment[:-1])])
    return index, state, None


def case_restart_last_hour():
    index = hours()
    index[240] = 0
    return index, all_active(), None


def case_restart_hour_238():
    t = hours()
    return np.where(t <= 238, 2 * t, t - 239), all_active(), None


def case_two_restarts():
    # only the last restart matters (drops at hours 100 and 200)
    t = hours()
    index = np.where(t <= 100, 5 * t, np.where(t <= 200, 3 * (t - 101), t - 201))
    return index, all_active(), None


def case_leading_missing_hours():
    t = hours()
    index = np.where(t < 100, -1, t - 100)
    state = np.where(t < 100, -1, ACTIVE)
    return index, state, None


def case_complete_never_restarted():
    # speed of the last active hours
    t = hours()
    index = np.where(t <= 100, t, 100)
    state = all_active()
    state[101:] = COMPLETE
    return index, state, None


def case_rerun_2_cycles():
    # drop 440 -> 438 at hour 220: not a restart
    # window 192..239 (48 hours) at 2 it/h, hour 220 clamped to 0 -> 47
    t = hours()
    index = np.where(t <= 220, 2 * t, 438 + 2 * (t - 221))
    return index, all_active(), None


def case_rerun_10_cycles():
    # drop 220 -> 210 at hour 220: not a restart, 47 increments in 48 hours
    t = hours()
    index = np.where(t <= 220, t, 210 + (t - 221))
    return index, all_active(), None


def case_restart_landing_at_2():
    # 3 it/h before, 1 it/h after: restart, 20 hours at 1 it/h
    t = hours()
    return np.where(t <= 219, 3 * t, 2 + (t - 220)), all_active(), None


def case_drop_landing_at_3():
    # same but landing at 3: not a restart
    # 27 hours at 3 it/h (192..218), hour 219 clamped, 20 hours at 1 it/h
    # -> 101 / 48 * 24 = 50.5
    t = hours()
    return np.where(t <= 219, 3 * t, 3 + (t - 220)), all_active(), None


def case_restart_across_gap_landing_at_1():
    # hours 201..205 missing, 34 hours at 1 it/h after the restart
    t = hours()
    index = np.where(t <= 200, 2 * t, 1 + (t - 206))
    state = all_active()
    index[201:206] = -1
    state[201:206] = -1
    return index, state, None


def case_gap_landing_at_3():
    # same gap but landing at 3: not a restart
    # 34 hours at 1 it/h (206..239) + 13 increments at 2 it/h (187..199)
    # -> 60 / 48 * 24 = 30
    t = hours()
    index = np.where(t <= 200, 2 * t, 3 + (t - 206))
    state = all_active()
    index[201:206] = -1
    state[201:206] = -1
    return index, state, None


def progress_reaches_end():
    # total is 200: 2 it/h until hour 98, index 199 at hour 99, then 200
    t = hours()
    return np.where(t <= 98, 2 * t, np.where(t == 99, 199, 200))


def case_end_then_queued():
    # window: 46 hours at 2 it/h + 3 + 1 -> 96 / 48 * 24 = 48
    t = hours()
    return progress_reaches_end(), np.where(t <= 99, ACTIVE, QUEUED), 200


def case_end_then_complete():
    t = hours()
    return progress_reaches_end(), np.where(t <= 99, ACTIVE, COMPLETE), 200


def case_end_then_restart():
    # restart at 0 at hour 220, then 2 it/h: 20 hours -> 48
    t = hours()
    index = np.where(t >= 220, 2 * (t - 220), progress_reaches_end())
    state = np.where(t <= 99, ACTIVE, np.where(t < 220, QUEUED, ACTIVE))
    return index, state, 200


def case_end_then_slow_restart():
    # restart at 0 at hour 220, then 1 it/h: 20 hours -> 24
    t = hours()
    index = np.where(t >= 220, t - 220, progress_reaches_end())
    state = np.where(t <= 99, ACTIVE, np.where(t < 220, QUEUED, ACTIVE))
    return index, state, 200


SPEED_CASES = [
    pytest.param(case_steady, {}, 24.0, id='a-steady'),
    pytest.param(case_restart_mid_run, {}, 24.0, id='b-restart-mid-run'),
    pytest.param(
        case_restart_across_missing_hours,
        {},
        24.0,
        id='c-restart-across-missing-hours',
    ),
    pytest.param(case_complete_then_restart, {}, 72.0, id='d-complete-then-restart'),
    pytest.param(
        case_complete_then_extended,
        {},
        43.0,
        id='e-complete-then-extended',
    ),
    pytest.param(case_aborted_suspended, {}, 14.0, id='f-none-excluded'),
    pytest.param(
        case_aborted_suspended,
        {'exclude_aborted': True},
        19.0,
        id='f-aborted-excluded',
    ),
    pytest.param(
        case_aborted_suspended,
        {'exclude_suspended': True},
        19.0,
        id='f-suspended-excluded',
    ),
    pytest.param(
        case_aborted_suspended,
        {'exclude_aborted': True, 'exclude_suspended': True},
        24.0,
        id='f-both-excluded',
    ),
    pytest.param(case_restart_last_hour, {}, 0.0, id='g-restart-last-hour'),
    pytest.param(case_restart_hour_238, {}, 24.0, id='h-restart-hour-238'),
    pytest.param(case_two_restarts, {}, 24.0, id='i-two-restarts'),
    pytest.param(case_leading_missing_hours, {}, 24.0, id='j-leading-missing-hours'),
    pytest.param(
        case_complete_never_restarted,
        {},
        23.5,
        id='l-complete-never-restarted',
    ),
    pytest.param(case_rerun_2_cycles, {}, 47.0, id='m-rerun-2-cycles'),
    pytest.param(case_rerun_10_cycles, {}, 23.5, id='n-rerun-10-cycles'),
    pytest.param(case_restart_landing_at_2, {}, 24.0, id='o-restart-landing-at-2'),
    pytest.param(case_drop_landing_at_3, {}, 50.5, id='p-drop-landing-at-3'),
    pytest.param(
        case_restart_across_gap_landing_at_1,
        {},
        24.0,
        id='q-restart-across-gap-landing-at-1',
    ),
    pytest.param(case_gap_landing_at_3, {}, 30.0, id='r-gap-landing-at-3'),
    pytest.param(case_end_then_queued, {}, 48.0, id='s-end-then-queued'),
    pytest.param(case_end_then_complete, {}, 48.0, id='s2-end-then-complete'),
    pytest.param(case_end_then_restart, {}, 48.0, id='t-end-then-restart'),
    pytest.param(
        case_end_then_slow_restart,
        {},
        24.0,
        id='t2-end-then-slow-restart',
    ),
    pytest.param(
        case_drop_landing_at_3,
        {'restart_max_index': 3},
        24.0,
        id='p-restart-max-index-3',
    ),
    pytest.param(
        case_drop_landing_at_3,
        {'restart_max_index': 2},
        50.5,
        id='p-restart-max-index-2',
    ),
    pytest.param(
        case_restart_landing_at_2,
        {'restart_max_index': 0},
        50.5,
        id='o-restart-max-index-0',
    ),
    pytest.param(
        case_restart_landing_at_2,
        {'restart_max_index': 1},
        50.5,
        id='o-restart-max-index-1',
    ),
]


@pytest.mark.parametrize(('build', 'options', 'expected'), SPEED_CASES)
def test_speed(build, options, expected):
    # each test builds its own dataset since get_summary modifies its input
    ds = make_ds(*build())
    assert speed(ds, **options) == pytest.approx(expected)


class StopError(Exception):
    pass


@pytest.mark.parametrize(
    ('extra', 'expected'),
    [
        pytest.param({}, 2, id='default'),
        pytest.param({'restart_max_index': 5}, 5, id='explicit'),
    ],
)
def test_show_summary_forwards_restart_max_index(
    tmp_path,
    monkeypatch,
    extra,
    expected,
):
    ds = make_ds(hours(), all_active())
    ds['suite'] = ('exp', ['x'])
    ds['experiment_type'] = ('exp', ['fc'])
    WorkingDirectory(tmp_path).save_report(ds.rename({'index': 'index_main'}))
    captured = {}

    def fake_get_summary(*args, **kwargs):
        # bind to the real signature, whether the value is passed by position or name
        bound = inspect.signature(get_summary).bind(*args, **kwargs)
        captured['restart_max_index'] = bound.arguments['restart_max_index']
        raise StopError

    monkeypatch.setattr(summary_main, 'get_summary', fake_get_summary)
    with pytest.raises(StopError):
        show_summary(
            tmp_path,
            suite='all',
            experiment_type='all',
            family='main',
            delta_t=DELTA_T,
            exclude_aborted=True,
            exclude_suspended=True,
            vref_fc=1,
            vref_lw=1,
            vref_elda=1,
            **extra,
        )
    assert captured['restart_max_index'] == expected
