- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Public Sub TABLA_CODAME(Accion As String, RutaLibroExcel As String, CAM_TABLA0 As CAMPOS_TABLA, CAM_AUXILIAR0 As CAMPOS_Auxiliar)
Dim Rango As Range
Dim Permiso As String
Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.HabilitarObjetos)
Dim NombreObjetos As Variant
Permiso = Rango.value
    ' Verificamos si el usuario tiene permisos de escritura
    If Permiso = "AMBAS" Or Permiso = "ESCRITURA" Then

        Dim X As Variant
        Dim RangoBorrado(0 To 1) As Range
        
        Dim Argumentos As String
        
        Dim i As Integer
        
            'NombreObjetoTablaSCS = "CodigoMOMENTCalculoSCS0"
        NombreObjetos = ObtieneNombreCodigoProcesaCalculoCODAME()
            ' Crear o asegurar la instancia de conexión a base de datos
        Call InstanciaObjetoBD

            ' Preparar argumentos para la llamada al proceso externo
        Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " & _
                     DatosTablaInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.NombreHoja, CAM_TABLA0.Tabla, RangoBorrado(0)) & " " & _
                     DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(1)) & " " & _
                     CAM_TABLA0.Tabla & " " & _
                     NombreObjetos(0) & " " & _
                     NombreObjetos(1)
                     


        ' Borramos el contenido de los rangos intermedios
        For i = 1 To 1
            If Not RangoBorrado(i) Is Nothing Then
                RangoBorrado(i).ClearContents
            End If
        Next i

        ' Ejecutar el proceso externo
        X = Shell(RutaAplicacionCodame & " " & Argumentos, vbMinimizedNoFocus)

    Else
        MsgBox "You do not have the necessary permissions to perform this action.", vbExclamation
    End If

End Sub


Public Function ObtieneNombreCodigoProcesaCalculoCODAME() As Variant
    Dim NombreBoton As String
    Dim NombreHoja As String
    Dim NombreObjetoProcesarCODAME As String
    Dim NombreObjetoClaseCODAME As String
    
    If TypeName(Application.Caller) = "String" Then
        NombreBoton = Application.Caller
    End If
    
    NombreHoja = ActiveSheet.Name
    
    Dim hoja As Worksheet
    Dim fila As Integer
    
    Set hoja = Worksheets("ObjetosTablaCodame")
    
    fila = 2
    While hoja.Cells(fila, 1).value <> NombreHoja
     
        fila = fila + 1
    Wend
    
    NombreObjetoProcesarCODAME = hoja.Cells(fila, 2).value
    NombreObjetoClaseCODAME = hoja.Cells(fila, 3).value

    ' Devolver como array
    ObtieneNombreCodigoProcesaCalculoCODAME = Array(NombreObjetoProcesarCODAME, NombreObjetoClaseCODAME)
End Function

-------------------------------------------------------------------------------
VBA MACRO Hoja1.cls 