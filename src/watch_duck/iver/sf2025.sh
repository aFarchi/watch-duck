module reset
module load iver

idl << EOF

set_plot,'ps' ; Workaround to prevent IDL looking for x-windows to interact with

exp = ['$1']

tag = 'tmp'

start_time = julday(01,01,2025,0,0,0)

end_time = julday($2,$3,2025,0,0,0)

forecast_only = [1]

grib_settings = {$
    dbasetime_days:6,basetime:[00],$
    air_params:['R','Q','Z','T','U','V']$
    }

stat_settings = {$
    regions_name: ['G','SH','TR','NH'],$
    regions_latitude: [[-90,90],[-90,-20],[-20,20],[20,90]],$
    regions_longitude: [[-180,180],[-180,180],[-180,180],[-180,180]]$
    }

reference = '0001'

profile = 'sf2025'

iver,$
    exp,$
    tag,$
    start_time = start_time,$
    end_time = end_time,$
    forecast_only = forecast_only,$
    grib_settings = grib_settings,$
    stat_settings = stat_settings,$
    reference = reference,$
    profile = profile,$
    /make_stats,$
    /nolatlon,$
    /noobstat,$
    /nospinup,$
    /notech,$
    /noweb,$
    /noupload,$
    /sfc,$
    /verbose

exit

EOF
