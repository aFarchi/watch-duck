module reset
module load iver$1

idl << EOF

set_plot,'ps' ; Workaround to prevent IDL looking for x-windows to interact with

exp = ['$2']

tag = '$3'

start_time = julday($4,0,0,0)

end_time = julday($5,0,0,0)

forecast_only = [$6]

grib_settings = {$
    dbasetime_days:$7,$
    basetime:[$8],$
    air_params:['R','Q','Z','T','U','V']$
    }

stat_settings = {$
    regions_name: ['G','SH','TR','NH'],$
    regions_latitude: [[-90,90],[-90,-20],[-20,20],[20,90]],$
    regions_longitude: [[-180,180],[-180,180],[-180,180],[-180,180]]$
    }

obstat_settings = {$
    show_stddev: 0$
    }

reference = '0001'

profile = '$9'

iver,$
    exp,$
    tag,$
    start_time = start_time,$
    end_time = end_time,$
    forecast_only = forecast_only,$
    grib_settings = grib_settings,$
    stat_settings = stat_settings,$
    obstat_settings = obstat_settings,$
    reference = reference,$
    profile = profile,$
    ${10}
    ${11}
    ${12}
    /make_stats,$
    /nolatlon,$
    /nospinup,$
    /noweb,$
    /noupload,$
    /sfc,$
    /verbose

exit

EOF
