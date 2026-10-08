- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Private NombreHoja_ As String
Private ListaProyectoAMS_ As String
Private ListaNormativa_ As String
Private ListaElectrodoSoldadura_ As String
Private ListaAceroEstructural_ As String
Private ListaEstandarTornillos_ As String
Private ListaCalculationTool_ As String
Private ListaSource_ As String
Private ListaDesignation_ As String
Private ListaCapacityMoment_ As String
Private ListaCapacityShear_ As String
Private ListaCapacityAxial_ As String
Private ListaCapacityShearSA_ As String
Private Tabla_ As String

Public Sub Inicializar(NombreHoja0 As String, ListaProyectoAMS0 As String, ListaNormativa0 As String, ListaElectrodoSoldadura0 As String, _
                             ListaAceroEstructural0 As String, ListaEstandarTornillos0 As String, ListaCalculationTool0 As String, ListaSource0 As String, _
                             ListaDesignation0 As String, Tabla0 As String, Optional ListaCapacityMoment0 As String, Optional ListaCapacityShear0 As String, Optional ListaCapacityAxial0 As String, _
                             Optional ListaCapacityShearSA0 As String)
    NombreHoja_ = NombreHoja0
    ListaProyectoAMS_ = ListaProyectoAMS0
    ListaNormativa_ = ListaNormativa0
    ListaElectrodoSoldadura_ = ListaElectrodoSoldadura0
    ListaAceroEstructural_ = ListaAceroEstructural0
    ListaEstandarTornillos_ = ListaEstandarTornillos0
    ListaCalculationTool_ = ListaCalculationTool0
    ListaSource_ = ListaSource0
    ListaDesignation_ = ListaDesignation0
    ListaCapacityMoment_ = ListaCapacityMoment0
    ListaCapacityShear_ = ListaCapacityShear0
    ListaCapacityAxial_ = ListaCapacityAxial0
    ListaCapacityShearSA_ = ListaCapacityShearSA0
    Tabla_ = Tabla0
End Sub

Property Get NombreHoja()

    NombreHoja = NombreHoja_

End Property
Property Get ListaNormativa()

    ListaNormativa = ListaNormativa_

End Property
Property Get ListaElectrodoSoldadura()

    ListaElectrodoSoldadura = ListaElectrodoSoldadura_

End Property
Property Get ListaAceroEstructural()

    ListaAceroEstructural = ListaAceroEstructural_

End Property
Property Get ListaEstandarTornillos()

    ListaEstandarTornillos = ListaEstandarTornillos_

End Property
Property Get ListaCalculationTool()

    ListaCalculationTool = ListaCalculationTool_

End Property
Property Get ListaSource()

    ListaSource = ListaSource_

End Property
Property Get ListaDesignation()

    ListaDesignation = ListaDesignation_

End Property

Property Get ListaProyectoAMS()

    ListaProyectoAMS = ListaProyectoAMS_

End Property
Property Get Tabla()

    Tabla = Tabla_

End Property

Property Get ListaCapacityMoment()

    ListaCapacityMoment = ListaCapacityMoment_

End Property

Property Get ListaCapacityShear()

    ListaCapacityShear = ListaCapacityShear_

End Property
Property Get ListaCapacityAxial()

    ListaCapacityAxial = ListaCapacityAxial_

End Property

Property Get ListaCapacityShearSA()
    ListaCapacityShearSA = ListaCapacityShearSA_
End Property






-------------------------------------------------------------------------------
VBA MACRO NombreExcel.cls 