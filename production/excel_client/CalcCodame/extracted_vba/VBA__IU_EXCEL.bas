- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Public Sub MOTOR_CALCULO_EXCEL()

    Dim CAM_TABLA0 As CAMPOS_TABLA
    Dim RutaLibroExcel As String
    Dim DatosMotorExcel As Variant

    RutaLibroExcel = ThisWorkbook.FullName

    Set CAM_TABLA0 = ObtieneCampoProcesarCALCEXCEL()
    DatosMotorExcel = ObtieneNombreCodigoProcesaCalculoEXCELENGINE()

    Call TABLA_EXCELENGINE("CALCULAR_EXCEL", RutaLibroExcel, CAM_TABLA0, DatosMotorExcel, ClaseNombreBD0.CAM_Auxiliar)


End Sub

Public Sub TABLA_EXCELENGINE(Accion As String, RutaLibroExcel As String, CAM_TABLA0 As CAMPOS_TABLA, NombreObjetos As Variant, CAM_AUXILIAR0 As CAMPOS_Auxiliar)

    Dim Rango As Range
    Dim Permiso As String
    'Dim NombreObjetos As Variant

    Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.HabilitarObjetos)
    Permiso = Rango.value

    If Permiso = "AMBAS" Or Permiso = "ESCRITURA" Then

        Dim X As Variant
        Dim RangoBorrado(0 To 1) As Range
        Dim Argumentos As String
        Dim i As Integer
        Dim ModoCalculo As String
        Dim RutaCopia As String

        'NombreObjetos = ObtieneNombreCodigoProcesaCalculoEXCELENGINE()
        
        ModoCalculo = ObtieneModoCalculoExcelEngine(RutaCopia)

        If ModoCalculo = "" Then
        Exit Sub
        End If

        Call InstanciaObjetoBD

        Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " & _
             DatosTablaInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.NombreHoja, CAM_TABLA0.Tabla, RangoBorrado(0)) & " " & _
             DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(1)) & " " & _
             CAM_TABLA0.Tabla & " " & _
             NombreObjetos(0) & " " & _
             ModoCalculo

        If ModoCalculo = "Copia" Then
            Argumentos = Argumentos & " " & Chr(34) & RutaCopia & Chr(34)
        End If

        For i = 1 To 1
            If Not RangoBorrado(i) Is Nothing Then
                RangoBorrado(i).ClearContents
            End If
        Next i
        
     
        X = Shell(Chr(34) & RutaAplicacionExcelEngine & Chr(34) & " " & Argumentos, vbMinimizedNoFocus)
        
    Else
        MsgBox "You do not have the necessary permissions to perform this action.", vbExclamation
    End If

End Sub


Public Function ObtieneNombreCodigoProcesaCalculoEXCELENGINE() As Variant

    Dim NombreHoja As String
    Dim NombreObjetoProcesarEXCEL As String
    Dim hoja As Worksheet
    Dim fila As Integer

    NombreHoja = ActiveSheet.Name

    Set hoja = Worksheets("ObjetosTablaExcelEngine")

    fila = 2
    While hoja.Cells(fila, 1).value <> NombreHoja
        fila = fila + 1
    Wend

    NombreObjetoProcesarEXCEL = hoja.Cells(fila, 2).value

    ObtieneNombreCodigoProcesaCalculoEXCELENGINE = Array(NombreObjetoProcesarEXCEL)

End Function

Public Sub SeleccionarRutaCalcExcelEngine()

    Dim Dialogo As FileDialog
    Dim NombreRuta As String

    NombreRuta = ObtieneNombreRutaExcelEngine()

    If NombreRuta = "" Then
        MsgBox "No se ha encontrado la configuración de ruta para esta hoja.", vbExclamation
        Exit Sub
    End If

    Set Dialogo = Application.FileDialog(msoFileDialogFolderPicker)

    With Dialogo
        .Title = "Seleccionar carpeta para guardar copias del motor de cálculo"
        .AllowMultiSelect = False

        If .Show = -1 Then
            ThisWorkbook.Names(NombreRuta).RefersToRange.value = .SelectedItems(1)
        End If
    End With

End Sub

Public Function ObtieneModoCalculoExcelEngine(ByRef RutaCopia As String) As String

    Dim ModoOperacion As String
    Dim NombreModoOperacion As String
    Dim NombreRuta As String

    NombreModoOperacion = ObtieneNombreModoOperacionExcelEngine()
    NombreRuta = ObtieneNombreRutaExcelEngine()

    If NombreModoOperacion = "" Or NombreRuta = "" Then
        MsgBox "No se ha encontrado la configuración del motor Excel para esta hoja.", vbExclamation
        ObtieneModoCalculoExcelEngine = ""
        Exit Function
    End If

    ModoOperacion = UCase(Trim(CStr(ThisWorkbook.Names(NombreModoOperacion).RefersToRange.value)))
    RutaCopia = Trim(CStr(ThisWorkbook.Names(NombreRuta).RefersToRange.value))

    If ModoOperacion = "NO" Then
        RutaCopia = ""
        ObtieneModoCalculoExcelEngine = "Normal"
        Exit Function
    End If

    If ModoOperacion = "SI" Then

        If RutaCopia = "" Or Dir(RutaCopia, vbDirectory) = "" Then
            MsgBox "Debe seleccionar una ruta válida para guardar las copias del motor de cálculo.", vbExclamation
            ObtieneModoCalculoExcelEngine = ""
            Exit Function
        End If

        ObtieneModoCalculoExcelEngine = "Copia"
        Exit Function

    End If

    MsgBox "El modo de operación debe ser SI o NO.", vbExclamation
    ObtieneModoCalculoExcelEngine = ""


End Function

Public Function ObtieneNombreModoOperacionExcelEngine() As String

    Select Case ActiveSheet.Name

        Case "IM_MOMENT_EXCEL"
            ObtieneNombreModoOperacionExcelEngine = "MODO_OPERACION_MOMENT"

        Case "IM_FLUSHEP_EXCEL"
            ObtieneNombreModoOperacionExcelEngine = "MODO_OPERACION_FLUSHEP"
            
        Case "IM_SHEAREP_EXCEL"
            ObtieneNombreModoOperacionExcelEngine = "MODO_OPERACION_SHEAREP"
            
        Case "IM_SPLICEEP_EXCEL"
            ObtieneNombreModoOperacionExcelEngine = "MODO_OPERACION_SPLICEEP"
            
        Case "IM_BRACING_EXCEL"
            ObtieneNombreModoOperacionExcelEngine = "MODO_OPERACION_BRACING"
        
        Case "IM_BRACINGEP_EXCEL"
            ObtieneNombreModoOperacionExcelEngine = "MODO_OPERACION_BRACINGEP"
        
        Case "IM_SPLICECP_EXCEL"
            ObtieneNombreModoOperacionExcelEngine = "MODO_OPERACION_SPLICECP"
            
        Case "IM_SHEAREXP_EXCEL"
            ObtieneNombreModoOperacionExcelEngine = "MODO_OPERACION_SHEAREXP"

        Case Else
            ObtieneNombreModoOperacionExcelEngine = ""

    End Select

End Function

Public Function ObtieneNombreRutaExcelEngine() As String

    Select Case ActiveSheet.Name

        Case "IM_MOMENT_EXCEL"
            ObtieneNombreRutaExcelEngine = "RUTA_MOMENT"

        Case "IM_FLUSHEP_EXCEL"
            ObtieneNombreRutaExcelEngine = "RUTA_FLUSHEP"
            
        Case "IM_SHEAREP_EXCEL"
            ObtieneNombreRutaExcelEngine = "RUTA_SHEAREP"

        Case "IM_SPLICEEP_EXCEL"
            ObtieneNombreRutaExcelEngine = "RUTA_SPLICEEP"
        
        Case "IM_BRACING_EXCEL"
            ObtieneNombreRutaExcelEngine = "RUTA_BRACING"
        
        Case "IM_BRACINGEP_EXCEL"
            ObtieneNombreRutaExcelEngine = "RUTA_BRACINGEP"

        Case "IM_SPLICECP_EXCEL"
            ObtieneNombreRutaExcelEngine = "RUTA_SPLICECP"
        
        Case "IM_SHEAREXP_EXCEL"
            ObtieneNombreRutaExcelEngine = "RUTA_SHEAREXP"
        
        Case Else
            ObtieneNombreRutaExcelEngine = ""

    End Select

End Function


Public Sub SeleccionarConexionesExcelEngine()

    Dim CAM_TABLA0 As CAMPOS_TABLA
    Dim Formulario As SeleccionConexionesExcelEngine

    Set CAM_TABLA0 = ObtieneCampoProcesarCALCEXCEL()

    Set Formulario = New SeleccionConexionesExcelEngine

    Call Formulario.Inicializar(CAM_TABLA0.NombreHoja, CAM_TABLA0.Tabla)

    Formulario.Show

End Sub
-------------------------------------------------------------------------------
VBA MACRO Hoja2.cls 