- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

Public CAM_MOMENT As CAMPOS_TABLA
Public CAM_MOMENT_CALC As CAMPOS_TABLA
Public CAM_MOMENT_CALC_EXCEL As CAMPOS_TABLA
Public CAM_MOMENT_CALC_MATHCAD As CAMPOS_TABLA
Public CAM_MOMENT_CALC_SCS As CAMPOS_TABLA
Public CAM_SPLICECP As CAMPOS_TABLA
Public CAM_SPLICECP_CALC As CAMPOS_TABLA
Public CAM_SPLICECP_CALC_EXCEL As CAMPOS_TABLA
Public CAM_SPLICECP_CALC_MATHCAD As CAMPOS_TABLA
Public CAM_SPLICECP_CALC_SCS As CAMPOS_TABLA
Public CAM_FLUSHEP As CAMPOS_TABLA
Public CAM_FLUSHEP_CALC As CAMPOS_TABLA
Public CAM_FLUSHEP_CALC_SCS As CAMPOS_TABLA
Public CAM_FLUSHEP_CALC_TEKLA As CAMPOS_TABLA
Public CAM_FLUSHEP_CALC_EXCEL As CAMPOS_TABLA
Public CAM_FLUSHEP_CALC_MATHCAD As CAMPOS_TABLA
Public CAM_BRACING As CAMPOS_TABLA
Public CAM_BRACING_CALC As CAMPOS_TABLA
Public CAM_BRACING_CALC_EXCEL As CAMPOS_TABLA
Public CAM_BRACING_CALC_MATHCAD As CAMPOS_TABLA
Public CAM_BRACING_CALC_SCS As CAMPOS_TABLA
Public CAM_BRACINGEP As CAMPOS_TABLA
Public CAM_BRACINGEP_CALC As CAMPOS_TABLA
Public CAM_BRACINGEP_CALC_EXCEL As CAMPOS_TABLA
Public CAM_BRACINGEP_CALC_MATHCAD As CAMPOS_TABLA
Public CAM_BRACINGEP_CALC_SCS As CAMPOS_TABLA
Public CAM_BRACINGHOR As CAMPOS_TABLA
Public CAM_BRACINGHOR_CALC As CAMPOS_TABLA
Public CAM_SPLICEEP As CAMPOS_TABLA
Public CAM_SPLICEEP_CALC As CAMPOS_TABLA
Public CAM_SPLICEEP_CALC_EXCEL As CAMPOS_TABLA
Public CAM_SPLICEEP_CALC_MATHCAD As CAMPOS_TABLA
Public CAM_SPLICEEP_CALC_SCS As CAMPOS_TABLA
Public CAM_SHEAREP As CAMPOS_TABLA
Public CAM_SHEAREP_CALC As CAMPOS_TABLA
Public CAM_SHEAREP_CALC_EXCEL As CAMPOS_TABLA
Public CAM_SHEAREP_CALC_MATHCAD As CAMPOS_TABLA
Public CAM_SHEAREP_CALC_SCS As CAMPOS_TABLA
Public CAM_SHEAREXP As CAMPOS_TABLA
Public CAM_SHEAREXP_CALC As CAMPOS_TABLA
Public CAM_SHEAREXP_CALC_EXCEL As CAMPOS_TABLA
Public CAM_SHEAREXP_CALC_MATHCAD As CAMPOS_TABLA
Public CAM_MW_CF As CAMPOS_TABLA
Public CAM_MW_CW As CAMPOS_TABLA
Public CAM_MW_B As CAMPOS_TABLA
Public CAM_MW_B02 As CAMPOS_TABLA
Public CAM_MW_B03 As CAMPOS_TABLA
Public CAM_MW_N As CAMPOS_TABLA
Public CAM_Auxiliar As CAMPOS_Auxiliar


Private Sub Class_Initialize()

Set CAM_MOMENT = New CAMPOS_TABLA
CAM_MOMENT.Inicializar "IU_MOMENT", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_MOMENT_1", "ListaCapacityMoment", "ListaCapacityShear", "ListaCapacityAxial", "ListaCapacityShearSA"

Set CAM_MOMENT_CALC = New CAMPOS_TABLA
CAM_MOMENT_CALC.Inicializar "IM_MOMENT", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_MOMENT_M1"

Set CAM_MOMENT_CALC_EXCEL = New CAMPOS_TABLA
CAM_MOMENT_CALC_EXCEL.Inicializar "IM_MOMENT_EXCEL", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_MOMENT_M2"

Set CAM_MOMENT_CALC_MATHCAD = New CAMPOS_TABLA
CAM_MOMENT_CALC_MATHCAD.Inicializar "IM_MOMENT_MATHCAD", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_MOMENT_M5"

Set CAM_MOMENT_CALC_SCS = New CAMPOS_TABLA
CAM_MOMENT_CALC_SCS.Inicializar "IM_MOMENT_SCS", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_MOMENT_M3"


Set CAM_SPLICECP = New CAMPOS_TABLA
CAM_SPLICECP.Inicializar "IU_SPLICECP", "Lista_ProyectosAMS_SPLICECP", "ListaNormativa_SPLICECP", "ListaElectrodoSoldadura_SPLICECP", "ListaAceroEstructural_SPLICECP", "ListaEstandarTornillos_SPLICECP", "ListaCalculationTool_SPLICECP", "ListaSource_SPLICECP", "ListaDesignation_SPLICECP", "Tabla_SPLICECP_1", "ListaCapacityMoment_SPLICECP", "ListaCapacityShear_SPLICECP", "ListaCapacityAxial_SPLICECP", "ListaCapacityShearSA_SPLICECP"

Set CAM_SPLICECP_CALC = New CAMPOS_TABLA
CAM_SPLICECP_CALC.Inicializar "IM_SPLICECP", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SPLICECP_M1"

Set CAM_SPLICECP_CALC_EXCEL = New CAMPOS_TABLA
CAM_SPLICECP_CALC_EXCEL.Inicializar "IM_SPLICECP_EXCEL", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SPLICECP_M2"

Set CAM_SPLICECP_CALC_MATHCAD = New CAMPOS_TABLA
CAM_SPLICECP_CALC_MATHCAD.Inicializar "IM_SPLICECP_MATHCAD", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SPLICECP_M5"

Set CAM_SPLICECP_CALC_SCS = New CAMPOS_TABLA
CAM_SPLICECP_CALC_SCS.Inicializar "IM_SPLICECP_SCS", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SPLICECP_M3"


Set CAM_FLUSHEP = New CAMPOS_TABLA
CAM_FLUSHEP.Inicializar "IU_FLUSHEP", "Lista_ProyectosAMS_FLUSHEP", "ListaNormativa_FLUSHEP", "ListaElectrodoSoldadura_FLUSHEP", "ListaAceroEstructural_FLUSHEP", "ListaEstandarTornillos_FLUSHEP", "ListaCalculationTool_FLUSHEP", "ListaSource_FLUSHEP", "ListaDesignation_FLUSHEP", "Tabla_FLUSHEP_1", "ListaCapacityMoment_FLUSHEP", "ListaCapacityShear_FLUSHEP", "ListaCapacityAxial_FLUSHEP", "ListaCapacityShearSA_FLUSHEP"

Set CAM_FLUSHEP_CALC = New CAMPOS_TABLA
CAM_FLUSHEP_CALC.Inicializar "IM_FLUSHEP", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_FLUSHEP_M1"

Set CAM_FLUSHEP_CALC_EXCEL = New CAMPOS_TABLA
CAM_FLUSHEP_CALC_EXCEL.Inicializar "IM_FLUSHEP_EXCEL", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_FLUSHEP_M2"

Set CAM_FLUSHEP_CALC_MATHCAD = New CAMPOS_TABLA
CAM_FLUSHEP_CALC_MATHCAD.Inicializar "IM_FLUSHEP_MATHCAD", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_FLUSHEP_M5"

Set CAM_FLUSHEP_CALC_SCS = New CAMPOS_TABLA
CAM_FLUSHEP_CALC_SCS.Inicializar "IM_FLUSHEP_SCS", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_FLUSHEP_M3"

Set CAM_FLUSHEP_CALC_TEKLA = New CAMPOS_TABLA
CAM_FLUSHEP_CALC_TEKLA.Inicializar "IM_FLUSHEP_TEKLA", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_FLUSHEP_M4"


Set CAM_BRACING = New CAMPOS_TABLA
CAM_BRACING.Inicializar "IU_BRACING", "Lista_ProyectosAMS_BRACING", "ListaNormativa_BRACING", "ListaElectrodoSoldadura_BRACING", "ListaAceroEstructural_BRACING", "ListaEstandarTornillos_BRACING", "ListaCalculationTool_BRACING", "ListaSource_BRACING", "ListaDesignation_BRACING", "Tabla_BRACING_1", "ListaCapacityMoment_BRACING", "ListaCapacityShear_BRACING", "ListaCapacityAxial_BRACING", "ListaCapacityShearSA_BRACING"

Set CAM_BRACING_CALC = New CAMPOS_TABLA
CAM_BRACING_CALC.Inicializar "IM_BRACING", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_BRACING_M1"

Set CAM_BRACING_CALC_EXCEL = New CAMPOS_TABLA
CAM_BRACING_CALC_EXCEL.Inicializar "IM_BRACING_EXCEL", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_BRACING_M2"

Set CAM_BRACING_CALC_MATHCAD = New CAMPOS_TABLA
CAM_BRACING_CALC_MATHCAD.Inicializar "IM_BRACING_MATHCAD", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_BRACING_M5"

Set CAM_BRACING_CALC_SCS = New CAMPOS_TABLA
CAM_BRACING_CALC_SCS.Inicializar "IM_BRACING_SCS", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_BRACING_M3"


Set CAM_BRACINGEP = New CAMPOS_TABLA
CAM_BRACINGEP.Inicializar "IU_BRACINGEP", "Lista_ProyectosAMS_BRACINGEP", "ListaNormativa_BRACINGEP", "ListaElectrodoSoldadura_BRACINGEP", "ListaAceroEstructural_BRACINGEP", "ListaEstandarTornillos_BRACINGEP", "ListaCalculationTool_BRACINGEP", "ListaSource_BRACINGEP", "ListaDesignation_BRACINGEP", "Tabla_BRACINGEP_1", "ListaCapacityMoment_BRACINGEP", "ListaCapacityShear_BRACINGEP", "ListaCapacityAxial_BRACINGEP", "ListaCapacityShearSA_BRACINGEP"

Set CAM_BRACINGEP_CALC = New CAMPOS_TABLA
CAM_BRACINGEP_CALC.Inicializar "IM_BRACINGEP", "Lista_ProyectosAMS_BRACINGEP", "ListaNormativa_BRACINGEP", "ListaElectrodoSoldadura_BRACINGEP", "ListaAceroEstructural_BRACINGEP", "ListaEstandarTornillos_BRACINGEP", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_BRACINGEP_M1"

Set CAM_BRACINGEP_CALC_EXCEL = New CAMPOS_TABLA
CAM_BRACINGEP_CALC_EXCEL.Inicializar "IM_BRACINGEP_EXCEL", "Lista_ProyectosAMS_BRACINGEP", "ListaNormativa_BRACINGEP", "ListaElectrodoSoldadura_BRACINGEP", "ListaAceroEstructural_BRACINGEP", "ListaEstandarTornillos_BRACINGEP", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_BRACINGEP_M2"

Set CAM_BRACINGEP_CALC_MATHCAD = New CAMPOS_TABLA
CAM_BRACINGEP_CALC_MATHCAD.Inicializar "IM_BRACINGEP_MATHCAD", "Lista_ProyectosAMS_BRACINGEP", "ListaNormativa_BRACINGEP", "ListaElectrodoSoldadura_BRACINGEP", "ListaAceroEstructural_BRACINGEP", "ListaEstandarTornillos_BRACINGEP", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_BRACINGEP_M5"

Set CAM_BRACINGEP_CALC_SCS = New CAMPOS_TABLA
CAM_BRACINGEP_CALC_SCS.Inicializar "IM_BRACINGEP_SCS", "Lista_ProyectosAMS_BRACINGEP", "ListaNormativa_BRACINGEP", "ListaElectrodoSoldadura_BRACINGEP", "ListaAceroEstructural_BRACINGEP", "ListaEstandarTornillos_BRACINGEP", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_BRACINGEP_M3"


Set CAM_BRACINGHOR = New CAMPOS_TABLA
CAM_BRACINGHOR.Inicializar "IU_BRACINGHOR", "Lista_ProyectosAMS_BRACINGHOR", "ListaNormativa_BRACINGHOR", "ListaElectrodoSoldadura_BRACINGHOR", "ListaAceroEstructural_BRACINGHOR", "ListaEstandarTornillos_BRACINGHOR", "ListaCalculationTool_BRACINGHOR", "ListaSource_BRACINGHOR", "ListaDesignation_BRACINGHOR", "Tabla_BRACINGHOR_1"

Set CAM_BRACINGHOR_CALC = New CAMPOS_TABLA
CAM_BRACINGHOR_CALC.Inicializar "IM_BRACINGHOR", "Lista_ProyectosAMS_BRACINGHOR", "ListaNormativa_BRACINGHOR", "ListaElectrodoSoldadura_BRACINGHOR", "ListaAceroEstructural_BRACINGHOR", "ListaEstandarTornillos_BRACINGHOR", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_BRACINGHOR_M1"


Set CAM_SPLICEEP = New CAMPOS_TABLA
CAM_SPLICEEP.Inicializar "IU_SPLICEEP", "Lista_ProyectosAMS_SPLICEEP", "ListaNormativa_SPLICEEP", "ListaElectrodoSoldadura_SPLICEEP", "ListaAceroEstructural_SPLICEEP", "ListaEstandarTornillos_SPLICEEP", "ListaCalculationTool_SPLICEEP", "ListaSource_SPLICEEP", "ListaDesignation_SPLICEEP", "Tabla_SPLICEEP_1", "ListaCapacityMoment_SPLICEEP", "ListaCapacityShear_SPLICEEP", "ListaCapacityAxial_SPLICEEP", "ListaCapacityShearSA_SPLICEEP"

Set CAM_SPLICEEP_CALC = New CAMPOS_TABLA
CAM_SPLICEEP_CALC.Inicializar "IM_SPLICEEP", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SPLICEEP_M1"

Set CAM_SPLICEEP_CALC_EXCEL = New CAMPOS_TABLA
CAM_SPLICEEP_CALC_EXCEL.Inicializar "IM_SPLICEEP_EXCEL", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SPLICEEP_M2"

Set CAM_SPLICEEP_CALC_MATHCAD = New CAMPOS_TABLA
CAM_SPLICEEP_CALC_MATHCAD.Inicializar "IM_SPLICEEP_MATHCAD", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SPLICEEP_M5"

Set CAM_SPLICEEP_CALC_SCS = New CAMPOS_TABLA
CAM_SPLICEEP_CALC_SCS.Inicializar "IM_SPLICEEP_SCS", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SPLICEEP_M3"


Set CAM_SHEAREP = New CAMPOS_TABLA
CAM_SHEAREP.Inicializar "IU_SHEAREP", "Lista_ProyectosAMS_SHEAREP", "ListaNormativa_SHEAREP", "ListaElectrodoSoldadura_SHEAREP", "ListaAceroEstructural_SHEAREP", "ListaEstandarTornillos_SHEAREP", "ListaCalculationTool_SHEAREP", "ListaSource_SHEAREP", "ListaDesignation_SHEAREP", "Tabla_SHEAREP_1", "ListaCapacityMoment_SHEAREP", "ListaCapacityShear_SHEAREP", "ListaCapacityAxial_SHEAREP", "ListaCapacityShearSA_SHEAREP"

Set CAM_SHEAREP_CALC = New CAMPOS_TABLA
CAM_SHEAREP_CALC.Inicializar "IM_SHEAREP", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SHEAREP_M1"

Set CAM_SHEAREP_CALC_EXCEL = New CAMPOS_TABLA
CAM_SHEAREP_CALC_EXCEL.Inicializar "IM_SHEAREP_EXCEL", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SHEAREP_M2"

Set CAM_SHEAREP_CALC_MATHCAD = New CAMPOS_TABLA
CAM_SHEAREP_CALC_MATHCAD.Inicializar "IM_SHEAREP_MATHCAD", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SHEAREP_M5"

Set CAM_SHEAREP_CALC_SCS = New CAMPOS_TABLA
CAM_SHEAREP_CALC_SCS.Inicializar "IM_SHEAREP_SCS", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SHEAREP_M3"


Set CAM_SHEAREXP = New CAMPOS_TABLA
CAM_SHEAREXP.Inicializar "IU_SHEAREXP", "Lista_ProyectosAMS_SHEAREXP", "ListaNormativa_SHEAREXP", "ListaElectrodoSoldadura_SHEAREXP", "ListaAceroEstructural_SHEAREXP", "ListaEstandarTornillos_SHEAREXP", "ListaCalculationTool_SHEAREXP", "ListaSource_SHEAREXP", "ListaDesignation_SHEAREXP", "Tabla_SHEAREXP_1", "ListaCapacityMoment_SHEAREXT", "ListaCapacityShear_SHEAREXT", "ListaCapacityAxial_SHEAREXT", "ListaCapacityShearSA_SHEAREXT"

Set CAM_SHEAREXP_CALC = New CAMPOS_TABLA
CAM_SHEAREXP_CALC.Inicializar "IM_SHEAREXP", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SHEAREXP_M1"

Set CAM_SHEAREXP_CALC_EXCEL = New CAMPOS_TABLA
CAM_SHEAREXP_CALC_EXCEL.Inicializar "IM_SHEAREXP_EXCEL", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SHEAREXP_M2"

Set CAM_SHEAREXP_CALC_MATHCAD = New CAMPOS_TABLA
CAM_SHEAREXP_CALC_MATHCAD.Inicializar "IM_SHEAREXP_MATHCAD", "ListaProyectoAMS", "ListaNormativa", "ListaElectrodoSoldadura", "ListaAceroEstructural", "ListaEstandarTornillos", "ListaCalculationTool", "ListaSource", "ListaDesignation", "Tabla_SHEAREXP_M5"


Set CAM_MW_CF = New CAMPOS_TABLA
CAM_MW_CF.Inicializar "MW_CF", "ListaProyectoAMS_MWCF", "ListaNormativa_MWCF", "ListaElectrodoSoldadura_MWCF", "ListaAceroEstructural_MWCF", "", "ListaCalculationTool_MWCF", "ListaSource_MWCF", "ListaDesignation_MWCF", "Tabla_MWCF_1", "ListaCapacityMoment_MWCF", "ListaCapacityShear_MWCF", "ListaCapacityAxial_MWCF", ""

Set CAM_MW_CW = New CAMPOS_TABLA
CAM_MW_CW.Inicializar "MW_CW", "ListaProyectoAMS_MWCW", "ListaNormativa_MWCW", "ListaElectrodoSoldadura_MWCW", "ListaAceroEstructural_MWCW", "", "ListaCalculationTool_MWCW", "ListaSource_MWCW", "ListaDesignation_MWCW", "Tabla_MWCW_1", "ListaCapacityMoment_MWCW", "ListaCapacityShear_MWCW", "ListaCapacityAxial_MWCW", ""

Set CAM_MW_B = New CAMPOS_TABLA
CAM_MW_B.Inicializar "MW_B", "ListaProyectoAMS_MWB", "ListaNormativa_MWB", "ListaElectrodoSoldadura_MWB", "ListaAceroEstructural_MWB", "", "ListaCalculationTool_MWB", "ListaSource_MWB", "ListaDesignation_MWB", "Tabla_MWB_1", "ListaCapacityMoment_MWB", "ListaCapacityShear_MWB", "ListaCapacityAxial_MWB", ""

Set CAM_MW_B02 = New CAMPOS_TABLA
CAM_MW_B02.Inicializar "MW_B02", "ListaProyectoAMS_MWB02", "ListaNormativa_MWB02", "ListaElectrodoSoldadura_MWB02", "ListaAceroEstructural_MWB02", "", "ListaCalculationTool_MWB02", "ListaSource_MWB02", "ListaDesignation_MWB02", "Tabla_MWB02_1", "ListaCapacityMoment_MWB02", "ListaCapacityShear_MWB02", "ListaCapacityAxial_MWB02", ""

Set CAM_MW_B03 = New CAMPOS_TABLA
CAM_MW_B03.Inicializar "MW_B03", "ListaProyectoAMS_MWB03", "ListaNormativa_MWB03", "ListaElectrodoSoldadura_MWB03", "ListaAceroEstructural_MWB03", "", "ListaCalculationTool_MWB03", "ListaSource_MWB03", "ListaDesignation_MWB03", "Tabla_MWB03_1", "ListaCapacityMoment_MWB03", "ListaCapacityShear_MWB03", "ListaCapacityAxial_MWB03", ""

Set CAM_MW_N = New CAMPOS_TABLA
CAM_MW_N.Inicializar "MW_N", "ListaProyectoAMS_MWN", "ListaNormativa_MWN", "ListaElectrodoSoldadura_MWN", "ListaAceroEstructural_MWN", "", "ListaCalculationTool_MWN", "ListaSource_MWN", "ListaDesignation_MWN", "Tabla_MWN_1", "ListaCapacityMoment_MWN", "ListaCapacityShear_MWN", "ListaCapacityAxial_MWN", ""

Set CAM_Auxiliar = New CAMPOS_Auxiliar

End Sub
-------------------------------------------------------------------------------
VBA MACRO Hoja20.cls 