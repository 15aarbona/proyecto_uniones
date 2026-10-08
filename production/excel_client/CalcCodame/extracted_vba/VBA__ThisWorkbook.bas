- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Public Sub HabilitarObjetos()

Dim X As Variant, RangoBorrado0 As Range, RangoBorrado1 As Range

Call InstanciaObjetoBD

Argumentos = "HABILITAR " & Chr(34) & RutaLibroExcel & Chr(34) & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, ClaseNombreBD0.CAM_Auxiliar.HabilitarObjetos, RangoBorrado0)
             '& DatosNombreInterfaz(Not EsLectura, ThisWorkbook, ClaseNombreBD0.CAM_Auxiliar.MensajeError, RangoBorrado1)

RangoBorrado0.ClearContents

X = Shell(RutaAplicacion + " " + Argumentos, vbMinimizedNoFocus)

End Sub



Private Sub Workbook_Open()

'Call OcultarRibbon
Call HabilitarObjetos

End Sub
-------------------------------------------------------------------------------
VBA MACRO Hoja11.cls 