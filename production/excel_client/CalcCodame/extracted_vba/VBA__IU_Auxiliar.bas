- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Function ObtenerMensajeEliminacionConexiones() As String
    Dim ListaNormativa As Range
    Dim ListaProyectoAMS As Range
    Dim normativaValores As String
    Dim proyectoValores As String
    Dim i As Long
    
    ' Obtener los rangos de las listas ListaNormativa y ListaProyectoAMS
    On Error Resume Next
    Set ListaNormativa = ThisWorkbook.Names(ClaseNombreBD0.CAM_MOMENT.ListaNormativa).RefersToRange
    Set ListaProyectoAMS = ThisWorkbook.Names(ClaseNombreBD0.CAM_MOMENT.ListaProyectoAMS).RefersToRange
    On Error GoTo 0

    ' Recorrer los valores de ListaNormativa
    normativaValores = ""
    For i = 1 To ListaNormativa.Rows.Count
        normativaValores = normativaValores & ListaNormativa.Cells(i, 1).value & ", "
    Next i
    If Len(normativaValores) > 0 Then
        normativaValores = Left(normativaValores, Len(normativaValores) - 2)
    End If

    ' Recorrer los valores de ListaProyectoAMS
    proyectoValores = ""
    For i = 1 To ListaProyectoAMS.Rows.Count
        proyectoValores = proyectoValores & ListaProyectoAMS.Cells(i, 1).value & ", "
    Next i
    If Len(proyectoValores) > 0 Then
        proyectoValores = Left(proyectoValores, Len(proyectoValores) - 2)
    End If

    ' Crear el mensaje final
    Dim mensaje As String
    mensaje = "¿Estás seguro de que quieres eliminar estas conexiones con Normativa: """ & normativaValores & """ y Proyecto: """ & proyectoValores & """?"

    ' Devolver el mensaje
    ObtenerMensajeEliminacionConexiones = mensaje
End Function


Public Sub ResetearFiltroNormativa()
    Range(ClaseNombreBD0.CAM_MOMENT.ListaNormativa).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICECP.ListaNormativa).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICEEP.ListaNormativa).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACING.ListaNormativa).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGEP.ListaNormativa).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_FLUSHEP.ListaNormativa).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGHOR.ListaNormativa).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREXP.ListaNormativa).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREP.ListaNormativa).value = "No Aplica"
End Sub

Public Sub ResetearFiltroAceroEstructural()
    Range(ClaseNombreBD0.CAM_MOMENT.ListaAceroEstructural).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICECP.ListaAceroEstructural).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICEEP.ListaAceroEstructural).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACING.ListaAceroEstructural).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGEP.ListaAceroEstructural).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_FLUSHEP.ListaAceroEstructural).value = "No Aplica"
        Range(ClaseNombreBD0.CAM_BRACINGHOR.ListaAceroEstructural).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREXP.ListaAceroEstructural).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREP.ListaAceroEstructural).value = "No Aplica"
End Sub

Public Sub ResetearFiltroElectrodoSoldadura()
    Range(ClaseNombreBD0.CAM_MOMENT.ListaElectrodoSoldadura).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICECP.ListaElectrodoSoldadura).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICEEP.ListaElectrodoSoldadura).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACING.ListaElectrodoSoldadura).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGEP.ListaElectrodoSoldadura).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_FLUSHEP.ListaElectrodoSoldadura).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGHOR.ListaElectrodoSoldadura).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREXP.ListaElectrodoSoldadura).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREP.ListaElectrodoSoldadura).value = "No Aplica"
End Sub

Public Sub ResetearFiltroEstandarTornillos()
    Range(ClaseNombreBD0.CAM_MOMENT.ListaEstandarTornillos).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICECP.ListaEstandarTornillos).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICEEP.ListaEstandarTornillos).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACING.ListaEstandarTornillos).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGEP.ListaEstandarTornillos).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_FLUSHEP.ListaEstandarTornillos).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGHOR.ListaEstandarTornillos).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREXP.ListaEstandarTornillos).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREP.ListaEstandarTornillos).value = "No Aplica"
End Sub

Public Sub ResetearFiltroProyecto()
    Range(ClaseNombreBD0.CAM_MOMENT.ListaProyectoAMS).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICECP.ListaProyectoAMS).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICEEP.ListaProyectoAMS).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACING.ListaProyectoAMS).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGEP.ListaProyectoAMS).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_FLUSHEP.ListaProyectoAMS).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGHOR.ListaProyectoAMS).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREXP.ListaProyectoAMS).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREP.ListaProyectoAMS).value = "No Aplica"
End Sub

Public Sub ResetearFiltroCalculationTool()
        Range(ClaseNombreBD0.CAM_MOMENT.ListaCalculationTool).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICECP.ListaCalculationTool).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICEEP.ListaCalculationTool).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACING.ListaCalculationTool).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGEP.ListaCalculationTool).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_FLUSHEP.ListaCalculationTool).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGHOR.ListaCalculationTool).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREXP.ListaCalculationTool).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREP.ListaAceroEstructural).value = "No Aplica"
    
End Sub

Public Sub ResetearFiltroSource()
        Range(ClaseNombreBD0.CAM_MOMENT.ListaSource).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICECP.ListaSource).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICEEP.ListaSource).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACING.ListaSource).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGEP.ListaSource).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_FLUSHEP.ListaSource).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGHOR.ListaSource).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREXP.ListaSource).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREP.ListaSource).value = "No Aplica"
    
End Sub

Public Sub ResetearFiltroDesignation()
        Range(ClaseNombreBD0.CAM_MOMENT.ListaDesignation).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICECP.ListaDesignation).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SPLICEEP.ListaDesignation).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACING.ListaDesignation).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGEP.ListaDesignation).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_FLUSHEP.ListaDesignation).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_BRACINGHOR.ListaDesignation).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREXP.ListaDesignation).value = "No Aplica"
    Range(ClaseNombreBD0.CAM_SHEAREP.ListaDesignation).value = "No Aplica"
    
End Sub

Sub CambiarHojaIU_to_CALC()
    Dim NombreHoja As String
    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IU_MOMENT"
            Sheets("IM_MOMENT").Activate
        Case "IU_FLUSHEP"
            Sheets("IM_FLUSHEP").Activate
        Case "IU_SPLICECP"
            Sheets("IM_SPLICECP").Activate
        Case "IU_SPLICEEP"
            Sheets("IM_SPLICEEP").Activate
        Case "IU_BRACING"
            Sheets("IM_BRACING").Activate
        Case "IU_BRACINGEP"
            Sheets("IM_BRACINGEP").Activate
        Case "IU_SHEAREP"
            Sheets("IM_SHEAREP").Activate
        Case "IU_SHEAREXP"
            Sheets("IM_SHEAREXP").Activate
        Case "IU_BRACINGHOR"
            Sheets("IM_BRACINGHOR").Activate
        Case Else
            MsgBox "Nombre de hoja no válido", vbExclamation
    End Select

End Sub


Sub CambiarHoja_to_IU()
    Dim NombreHoja As String
    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IM_MOMENT"
            Sheets("IU_MOMENT").Activate
        Case "IM_FLUSHEP"
            Sheets("IU_FLUSHEP").Activate
        Case "IM_SPLICECP"
            Sheets("IU_SPLICECP").Activate
        Case "IM_SPLICEEP"
            Sheets("IU_SPLICEEP").Activate
        Case "IM_BRACING"
            Sheets("IU_BRACING").Activate
        Case "IM_BRACINGEP"
            Sheets("IU_BRACINGEP").Activate
        Case "IM_SHEAREP"
            Sheets("IU_SHEAREP").Activate
        Case "IM_SHEAREXP"
            Sheets("IU_SHEAREXP").Activate
        Case "IM_BRACINGHOR"
            Sheets("IU_BRACINGHOR").Activate
        Case Else
            MsgBox "Nombre de hoja no válido", vbExclamation
    End Select

End Sub

Sub CambiarHojaIU_to_CALC_Jorge()
    Dim NombreHoja As String
    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IU_MOMENT"
            Sheets("IM_MOMENT_EXCEL").Activate
        Case "IU_FLUSHEP"
            Sheets("IM_FLUSHEP_EXCEL").Activate
        Case "IU_SPLICECP"
            Sheets("IM_SPLICECP_EXCEL").Activate
        Case "IU_SPLICEEP"
            Sheets("IM_SPLICEEP_EXCEL").Activate
        Case "IU_BRACING"
            Sheets("IM_BRACING_EXCEL").Activate
        Case "IU_BRACINGEP"
            Sheets("IM_BRACINGEP_EXCEL").Activate
        Case "IU_SHEAREP"
            Sheets("IM_SHEAREP_EXCEL").Activate
        Case "IU_SHEAREXP"
            Sheets("IM_SHEAREXP_EXCEL").Activate
        Case "IU_BRACINGHOR"
            Sheets("IM_BRACINGHOR_EXCEL").Activate
        Case Else
            MsgBox "Nombre de hoja no válido", vbExclamation
    End Select

End Sub


Sub CambiarIndice_to_IU()
    Dim NombreRectangulo As String
    Dim NombreHojaDestino As String
    Dim hoja As Worksheet
    Dim hayOtrasVisibles As Boolean

    ' Verifica que sea llamada desde un botón o forma
    If TypeName(Application.Caller) = "String" Then
        NombreRectangulo = Application.Caller
    Else
        MsgBox "Esta macro debe ser llamada desde un botón o forma.", vbExclamation
        Exit Sub
    End If

    ' Mapeo del rectángulo al nombre de hoja destino
    Select Case NombreRectangulo
        Case "Rectangulo_FLUSHEP":     NombreHojaDestino = "IU_FLUSHEP"
        Case "Rectangulo_MOMENT":      NombreHojaDestino = "IU_MOMENT"
        Case "Rectangulo_SPLICECP":    NombreHojaDestino = "IU_SPLICECP"
        Case "Rectangulo_SPLICEEP":    NombreHojaDestino = "IU_SPLICEEP"
        Case "Rectangulo_BRACING":     NombreHojaDestino = "IU_BRACING"
        Case "Rectangulo_BRACINGEP":   NombreHojaDestino = "IU_BRACINGEP"
        Case "Rectangulo_SHEAREP":     NombreHojaDestino = "IU_SHEAREP"
        Case "Rectangulo_SHEAREXP":    NombreHojaDestino = "IU_SHEAREXP"
        Case "Rectangulo_BRACINGHOR":  NombreHojaDestino = "IU_BRACINGHOR"
        Case Else
            MsgBox "Nombre de hoja no válido: " & NombreRectangulo, vbExclamation
            Exit Sub
    End Select

    ' Verificar si hay otras hojas visibles que no sean la destino ni INDEX
    hayOtrasVisibles = False
    For Each hoja In ThisWorkbook.Worksheets
        If hoja.Visible = xlSheetVisible Then
            If hoja.Name <> NombreHojaDestino And hoja.Name <> "INDEX" Then
                hayOtrasVisibles = True
                Exit For
            End If
        End If
    Next hoja

    ' Solo ocultar si hay otras visibles distintas a la destino o INDEX
    If hayOtrasVisibles Then
        Application.ScreenUpdating = False
        For Each hoja In ThisWorkbook.Worksheets
            If hoja.Name <> NombreHojaDestino And hoja.Name <> "INDEX" Then
                hoja.Visible = xlSheetHidden
            End If
        Next hoja
        Application.ScreenUpdating = True
    End If

    ' Mostrar y activar la hoja destino
    With Sheets(NombreHojaDestino)
        If .Visible <> xlSheetVisible Then .Visible = xlSheetVisible
        .Activate
    End With
End Sub




Sub IrAHoja_IM_SCS()
    Dim HojaActual As Worksheet
    Dim nombreActual As String
    Dim nombreDestino As String
    Dim hojasPermitidas As Variant
    Dim i As Long
    
    Set HojaActual = ActiveSheet
    nombreActual = HojaActual.Name
    
    ' Lista de hojas IU permitidas
    hojasPermitidas = Array( _
        "IU_FLUSHEP", "IU_MOMENT", "IU_SPLICECP", "IU_SPLICEEP", _
        "IU_BRACING", "IU_BRACINGEP", "IU_SHEAREP", "IU_SHEAREXP", "IU_BRACINGHOR" _
    )
    
    ' Comprobar si está en la lista
    For i = LBound(hojasPermitidas) To UBound(hojasPermitidas)
        If nombreActual = hojasPermitidas(i) Then
            nombreDestino = Replace(nombreActual, "IU_", "IM_") & "_SCS"
            
            ' Verificar si existe la hoja destino
            On Error Resume Next
            If Not Worksheets(nombreDestino) Is Nothing Then
                Worksheets(nombreDestino).Visible = xlSheetVisible
                Worksheets(nombreDestino).Activate
            Else
                MsgBox "La hoja '" & nombreDestino & "' no existe.", vbExclamation
            End If
            On Error GoTo 0
            
            Exit Sub
        End If
    Next i

    MsgBox "Esta hoja no tiene una hoja IM_..._SCS asociada.", vbInformation
End Sub

Sub IrAHoja_IU()
    Dim HojaActual As Worksheet
    Dim nombreActual As String
    Dim nombreDestino As String
    
    Set HojaActual = ActiveSheet
    nombreActual = HojaActual.Name
    
    ' Comprobar que el nombre empieza por "IM_" y termina en "_SCS"
    If Left(nombreActual, 3) = "IM_" And Right(nombreActual, 4) = "_SCS" Then
        ' Extraer el nombre intermedio para construir el nombre IU_
        nombreDestino = "IU_" & Mid(nombreActual, 4, Len(nombreActual) - 7)
        
        On Error Resume Next
        If Not Worksheets(nombreDestino) Is Nothing Then
            ' Mostrar y activar la hoja IU
            Worksheets(nombreDestino).Visible = xlSheetVisible
            Worksheets(nombreDestino).Activate
            
            ' Ocultar la hoja IM que dejamos (oculto normal)
            HojaActual.Visible = xlSheetHidden
        Else
            MsgBox "La hoja '" & nombreDestino & "' no existe.", vbExclamation
        End If
        On Error GoTo 0
    Else
        MsgBox "Esta hoja no es una hoja IM_..._SCS válida.", vbInformation
    End If
End Sub


Sub MostrarIndex()
    With Sheets("INDEX")
        .Visible = xlSheetVisible
        .Activate
    End With
End Sub


Sub CambiarIU_to_Indice()
    Sheets("INDEX").Activate
End Sub
    


Sub BorrarContenidoTabla()
    Dim ws As Worksheet
    Dim tbl As ListObject
    
    ' Establece la hoja activa
    Set ws = ActiveSheet
    
    ' Bucle por todas las tablas de la hoja activa
    For Each tbl In ws.ListObjects
        ' Borra el contenido de la tabla, sin eliminar encabezados ni formato
        If Not tbl.DataBodyRange Is Nothing Then
            tbl.DataBodyRange.ClearContents
        End If
    Next tbl
End Sub


Public Sub OcultarHojaDeFormaSegura()
    Sheets("Prueba").Visible = xlSheetVeryHidden
End Sub

'Public Sub MostrarHojaPrivada()
    'Sheets("Prueba").Visible = xlSheetVisible
'End Sub

Sub OcultarRibbon()
    Application.ExecuteExcel4Macro "SHOW.TOOLBAR(""Ribbon"", False)"
End Sub

Sub MostrarRibbon()
    Application.ExecuteExcel4Macro "SHOW.TOOLBAR(""Ribbon"", True)"
End Sub
Sub Settings()
    Dim nombreForma As String
    Dim hojaDestino As Worksheet

    ' Obtener el nombre de la forma que se ha hecho clic
    On Error Resume Next
    nombreForma = Application.Caller
    On Error GoTo 0

    ' Determinar la hoja destino según el nombre de la forma
    Select Case nombreForma
        Case "Imagen_HELP", "rectangulo_HELP_1", "rectangulo_HELP_2"
            Set hojaDestino = ThisWorkbook.Sheets("HELP")
        Case "Imagen_FAQs", "rectangulo_FAQs_1", "rectangulo_FAQs_2"
            Set hojaDestino = ThisWorkbook.Sheets("FAQs")
        Case "Imagen_PREFERENCES", "rectangulo_PREFERENCES_1", "rectangulo_PREFERENCES_2"
            Set hojaDestino = ThisWorkbook.Sheets("PREFERENCES")
        Case "Imagen_DOCUMENTATION", "rectangulo_DOCUMENTATION_1", "rectangulo_DOCUMENTATION_2"
            Set hojaDestino = ThisWorkbook.Sheets("DOCUMENTATION")
        Case Else
            MsgBox "No se encontró la hoja correspondiente.", vbExclamation
            Exit Sub
    End Select

    ' Mostrar y activar la hoja si se asignó correctamente
    If Not hojaDestino Is Nothing Then
        If hojaDestino.Visible = xlSheetHidden Or hojaDestino.Visible = xlSheetVeryHidden Then
            hojaDestino.Visible = xlSheetVisible
        End If
        hojaDestino.Activate
    End If
End Sub


Sub BackIndex()
    With ThisWorkbook.Sheets("HELP")
        .Visible = xlSheetHidden
    End With
    
    With ThisWorkbook.Sheets("FAQs")
        .Visible = xlSheetHidden
    End With
    
    With ThisWorkbook.Sheets("FAQs_Spain")
        .Visible = xlSheetHidden
    End With
    
    With ThisWorkbook.Sheets("PREFERENCES")
        .Visible = xlSheetHidden
    End With
    
    With ThisWorkbook.Sheets("DOCUMENTATION")
        .Visible = xlSheetHidden
    End With

    With ThisWorkbook.Sheets("INDEX")
        If .Visible = xlSheetHidden Or .Visible = xlSheetVeryHidden Then
            .Visible = xlSheetVisible
        End If
        .Activate
    End With
End Sub


Sub Traducir()
    With ThisWorkbook.Sheets("FAQs")
        .Visible = xlSheetHidden
    End With
    
    With ThisWorkbook.Sheets("FAQs_Spain")
        If .Visible = xlSheetHidden Or .Visible = xlSheetVeryHidden Then
            .Visible = xlSheetVisible
        End If
        .Activate
    End With
End Sub

Sub Traduce()
    With ThisWorkbook.Sheets("FAQs_Spain")
        .Visible = xlSheetHidden
    End With
    
    With ThisWorkbook.Sheets("FAQs")
        If .Visible = xlSheetHidden Or .Visible = xlSheetVeryHidden Then
            .Visible = xlSheetVisible
        End If
        .Activate
    End With
End Sub
-------------------------------------------------------------------------------
VBA MACRO Auxiliar.bas 