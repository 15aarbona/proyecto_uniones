- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Private Sub Worksheet_Activate()

Call InstanciaObjetoBD

End Sub

Private Sub Worksheet_Change(ByVal Target As Range)

Dim Rango As Range
Dim Colu, fila As Integer

Colu = Target.column
fila = Target.Row

Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.MensajeError)

If Target.column = Rango.column And Target.Row = Rango.Row Then

    Dim mensaje As String
    mensaje = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.MensajeError).value

    If mensaje <> "" Then
        MsgBox (mensaje)
    End If

End If

Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.HabilitarObjetos)

If Target.column = Rango.column And Target.Row = Rango.Row Then
    
    
    
    'Call MostrarHojaPrivada

    'If mensaje <> "" Then
       ' MsgBox " WELCOME to CONNEXTOR " & vbCrLf & vbCrLf & _
       '"Access granted for: " & Rango.Value, vbInformation, "CONNEXTOR Access"

    'End If

End If



'Para la insercion de conexiones en la BBDD
Dim RangoUnicode As Range
Set RangoUnicode = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.MensajeAdvertenciaUnicode)

Dim NombreObjetoTablaBD As String
Dim mensajeUnicode As String

If Target.column = RangoUnicode.column And Target.Row = RangoUnicode.Row Then

    'Leer nombre hoja de la celda de AUXILIAR
    NombreObjetoTablaBD = ObtieneNombreObjetoTablaBD()
    Set CAM_TABLA0 = ObtieneCampoTabla()

    mensajeUnicode = RangoUnicode.value
    If mensajeUnicode <> "" Then
        mensajeUnicode = "These connections are available in the connections database. Do you want to overwrite them?"
        ' Mostrar el cuadro de mensaje con dos opciones: Sí o No
        respuesta = MsgBox(mensajeUnicode, vbYesNo + vbQuestion, "Advertencia")
        ' Verificar la respuesta del usuario
        If respuesta = vbYes Then
            Call TABLA_ELIMINAR("ELIMINAR", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar, NombreObjetoTablaBD)
            Call TABLA_INSERTAR("INSERTAR", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar, "MOMENT", NombreObjetoTablaBD)
            MsgBox "Connections successfully updated.", vbInformation, "Operation."
            Else
            MsgBox "Operation cancelled.", vbExclamation, "Cancelled."

        End If
    End If
End If
    
'Para la insercion de conexiones en la BBDD de AMS
Dim RangoUnicodeAMS As Range
Set RangoUnicodeAMS = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.MensajeAdvertenciaUnicodeAMS)

If Target.column = RangoUnicodeAMS.column And Target.Row = RangoUnicodeAMS.Row Then

    'Leer nombre hoja de la celda de AUXILIAR
    NombreObjetoTablaBD = ObtieneNombreObjetoTablaBD()
    Set CAM_TABLA0 = ObtieneCampoTabla()
    mensajeUnicode = RangoUnicodeAMS.value
    If mensajeUnicode <> "" Then
        mensajeUnicode = "These connections are available in the connections database. Do you want to overwrite them?"
        ' Mostrar el cuadro de mensaje con dos opciones: Sí o No
        respuesta = MsgBox(mensajeUnicode, vbYesNo + vbQuestion, "Advertencia")
        ' Verificar la respuesta del usuario
        If respuesta = vbYes Then
            Call TABLA_ELIMINAR_AMS("ELIMINAR_AMS", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar, NombreObjetoTablaBD)
            Call TABLA_INSERTAR_AMS("INSERTAR_AMS", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar, NombreObjetoTablaBD)
            MsgBox "Connections successfully updated.", vbInformation, "Operation."
            Else
            MsgBox "Operation cancelled.", vbExclamation, "Cancelled."

        End If
    End If
End If



Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreProyectos)

If Target.column = Rango.column And Target.Row = Rango.Row Then

    If Target.Cells(1, 1).value <> "" Then Call RehacerNombreLista(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreProyectos, ClaseNombreBD0.CAM_Auxiliar.Lista_NombreProyectosAcotada)

End If

Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreNormativa)

If Target.column = Rango.column And Target.Row = Rango.Row Then

    If Target.Cells(1, 1).value <> "" Then Call RehacerNombreLista(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreNormativa, ClaseNombreBD0.CAM_Auxiliar.Lista_NombreNormativaAcotada)

End If

Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreAceroEstructural)

If Target.column = Rango.column And Target.Row = Rango.Row Then

    If Target.Cells(1, 1).value <> "" Then Call RehacerNombreLista(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreAceroEstructural, ClaseNombreBD0.CAM_Auxiliar.Lista_NombreAceroEstructuralAcotada)

End If

Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreElectrodoSoldadura)

If Target.column = Rango.column And Target.Row = Rango.Row Then

    If Target.Cells(1, 1).value <> "" Then Call RehacerNombreLista(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreElectrodoSoldadura, ClaseNombreBD0.CAM_Auxiliar.Lista_NombreElectrodoSoldaduraAcotada)

End If

Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreEstandarTornillos)


Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreEstandarTornillos)

If Target.column = Rango.column And Target.Row = Rango.Row Then

    If Target.Cells(1, 1).value <> "" Then Call RehacerNombreLista(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreEstandarTornillos, ClaseNombreBD0.CAM_Auxiliar.Lista_NombreEstandarTornillosAcotada)

End If


Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreCalculationTool)
If Target.column = Rango.column And Target.Row = Rango.Row Then

    If Target.Cells(1, 1).value <> "" Then Call RehacerNombreLista(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreCalculationTool, ClaseNombreBD0.CAM_Auxiliar.Lista_NombreCalculationToolAcotada)

End If

Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreSource)
If Target.column = Rango.column And Target.Row = Rango.Row Then

    If Target.Cells(1, 1).value <> "" Then Call RehacerNombreLista(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreSource, ClaseNombreBD0.CAM_Auxiliar.Lista_NombreSourceAcotada)

End If

Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreDesignation)
If Target.column = Rango.column And Target.Row = Rango.Row Then

    If Target.Cells(1, 1).value <> "" Then Call RehacerNombreLista(ClaseNombreBD0.CAM_Auxiliar.Lista_NombreDesignation, ClaseNombreBD0.CAM_Auxiliar.Lista_NombreDesignationAcotada)

End If

End Sub







-------------------------------------------------------------------------------
VBA MACRO CAMPOS_Auxiliar.cls 