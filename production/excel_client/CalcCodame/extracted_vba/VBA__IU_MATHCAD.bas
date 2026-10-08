- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

Public Sub MOTOR_CALCULO_MATHCAD()

    Dim RutaLibroExcel As String
    Dim DatosMotorMathcad As Variant
    Dim NombreHoja As String
    Dim NombreTabla As String

    RutaLibroExcel = ThisWorkbook.FullName

    If Not ObtieneDatosTablaMathcad(NombreHoja, NombreTabla) Then Exit Sub

    DatosMotorMathcad = ObtieneNombreCodigoProcesaCalculoMATHCAD()
    If CStr(DatosMotorMathcad(0)) = "" Then Exit Sub

    Call TABLA_MATHCAD("CALCULAR_MATHCAD", RutaLibroExcel, NombreHoja, NombreTabla, DatosMotorMathcad, ClaseNombreBD0.CAM_Auxiliar)

End Sub


Public Sub TABLA_MATHCAD(Accion As String, RutaLibroExcel As String, NombreHoja As String, NombreTabla As String, NombreObjetos As Variant, CAM_AUXILIAR0 As CAMPOS_Auxiliar)

    Dim Rango As Range
    Dim Permiso As String
    Dim X As Variant
    Dim RangoBorrado(0 To 1) As Range
    Dim Argumentos As String
    Dim i As Integer
    Dim ModoCalculo As String
    Dim RutaCopia As String
    Dim RutaAplicacion As String

    Set Rango = Hoja6.Range(CAM_AUXILIAR0.HabilitarObjetos)
    Permiso = CStr(Rango.value)

    If Permiso = "AMBAS" Or Permiso = "ESCRITURA" Then

        ModoCalculo = ObtieneModoCalculoMathcad(RutaCopia)
        If ModoCalculo = "" Then Exit Sub

        Call InstanciaObjetoBD
        
        RutaAplicacion = RutaAplicacionMathcad

        Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " & _
            DatosTablaInterfaz(EsLectura, ThisWorkbook, NombreHoja, NombreTabla, RangoBorrado(0)) & " " & _
            DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(1)) & " " & _
            NombreTabla & " " & _
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

        X = Shell(Chr(34) & RutaAplicacion & Chr(34) & " " & Argumentos, vbMinimizedNoFocus)

    Else
        MsgBox "You do not have the necessary permissions to perform this action.", vbExclamation
    End If

End Sub


Public Function ObtieneNombreCodigoProcesaCalculoMATHCAD() As Variant

    Dim NombreTipologia As String

    Select Case ActiveSheet.Name

        Case "IM_MOMENT_MATHCAD"
            NombreTipologia = "MOMENT"

        Case "IM_FLUSHEP_MATHCAD"
            NombreTipologia = "FLUSHEP"
            
        Case "IM_SHEAREP_MATHCAD"
            NombreTipologia = "SHEAREP"
        
        Case "IM_SHEAREXP_MATHCAD"
            NombreTipologia = "SHEAREXP"
            
        Case "IM_SPLICEEP_MATHCAD"
            NombreTipologia = "SPLICEEP"
        
        Case "IM_SPLICECP_MATHCAD"
            NombreTipologia = "SPLICECP"
        
        Case "IM_BRACING_MATHCAD"
            NombreTipologia = "BRACING"
        
        Case "IM_BRACINGEP_MATHCAD"
            NombreTipologia = "BRACINGEP"


        Case Else
            MsgBox "No existe configuracion Mathcad para la hoja " & ActiveSheet.Name & ".", vbExclamation
            NombreTipologia = ""

    End Select

    ObtieneNombreCodigoProcesaCalculoMATHCAD = Array(NombreTipologia)

End Function


Public Sub SeleccionarRutaCalcMathcad()

    Dim Dialogo As FileDialog
    Dim NombreRuta As String
    Dim RangoRuta As Range

    NombreRuta = ObtieneNombreRutaMathcad()

    If NombreRuta = "" Then
        MsgBox "No se ha encontrado la configuracion de ruta para esta hoja.", vbExclamation
        Exit Sub
    End If

    Set RangoRuta = ObtieneRangoNombreLibro(NombreRuta)

    If RangoRuta Is Nothing Then
        MsgBox "No existe el nombre definido " & NombreRuta & ".", vbExclamation
        Exit Sub
    End If

    Set Dialogo = Application.FileDialog(msoFileDialogFolderPicker)

    With Dialogo
        .Title = "Seleccionar carpeta para guardar copias del motor Mathcad"
        .AllowMultiSelect = False

        If .Show = -1 Then
            RangoRuta.value = .SelectedItems(1)
        End If
    End With

End Sub


Public Function ObtieneModoCalculoMathcad(ByRef RutaCopia As String) As String

    Dim ModoOperacion As String
    Dim NombreModoOperacion As String
    Dim NombreRuta As String
    Dim RangoModo As Range
    Dim RangoRuta As Range

    NombreModoOperacion = ObtieneNombreModoOperacionMathcad()
    NombreRuta = ObtieneNombreRutaMathcad()

    If NombreModoOperacion = "" Or NombreRuta = "" Then
        MsgBox "No se ha encontrado la configuracion del motor Mathcad " & "para esta hoja.", vbExclamation
        Exit Function
    End If

    Set RangoModo = ObtieneRangoNombreLibro(NombreModoOperacion)
    Set RangoRuta = ObtieneRangoNombreLibro(NombreRuta)

    If RangoModo Is Nothing Or RangoRuta Is Nothing Then
        MsgBox "No se encuentran los nombres definidos de modo y ruta.", vbExclamation
        Exit Function
    End If

    ModoOperacion = UCase$(Trim$(CStr(RangoModo.value)))
    RutaCopia = Trim$(CStr(RangoRuta.value))

    If ModoOperacion = "NO" Then
        RutaCopia = ""
        ObtieneModoCalculoMathcad = "Normal"
        Exit Function
    End If

    If ModoOperacion = "SI" Then
        If RutaCopia = "" Or Not CarpetaExiste(RutaCopia) Then
            MsgBox "Debe seleccionar una ruta valida para guardar las copias " & "del motor Mathcad.", vbExclamation
            Exit Function
        End If

        ObtieneModoCalculoMathcad = "Copia"
        Exit Function
    End If

    MsgBox "El modo de operacion debe ser SI o NO.", vbExclamation

End Function


Public Function ObtieneNombreModoOperacionMathcad() As String

    Select Case ActiveSheet.Name

        Case "IM_MOMENT_MATHCAD"
            ObtieneNombreModoOperacionMathcad = "MODO_OPERACION_MOMENT_MATHCAD"

        Case "IM_FLUSHEP_MATHCAD"
            ObtieneNombreModoOperacionMathcad = "MODO_OPERACION_FLUSHEP_MATHCAD"
        
        Case "IM_SHEAREP_MATHCAD"
            ObtieneNombreModoOperacionMathcad = "MODO_OPERACION_SHEAREP_MATHCAD"
        
        Case "IM_SHEAREXP_MATHCAD"
            ObtieneNombreModoOperacionMathcad = "MODO_OPERACION_SHEAREXP_MATHCAD"
        
        Case "IM_SPLICEEP_MATHCAD"
            ObtieneNombreModoOperacionMathcad = "MODO_OPERACION_SPLICEEP_MATHCAD"
            
        Case "IM_SPLICECP_MATHCAD"
            ObtieneNombreModoOperacionMathcad = "MODO_OPERACION_SPLICECP_MATHCAD"
            
        Case "IM_BRACING_MATHCAD"
            ObtieneNombreModoOperacionMathcad = "MODO_OPERACION_BRACING_MATHCAD"
        
        Case "IM_BRACINGEP_MATHCAD"
            ObtieneNombreModoOperacionMathcad = "MODO_OPERACION_BRACINGEP_MATHCAD"
            

        Case Else
            ObtieneNombreModoOperacionMathcad = ""

    End Select

End Function


Public Function ObtieneNombreRutaMathcad() As String

    Select Case ActiveSheet.Name

        Case "IM_MOMENT_MATHCAD"
            ObtieneNombreRutaMathcad = "RUTA_MOMENT_MATHCAD"

        Case "IM_FLUSHEP_MATHCAD"
            ObtieneNombreRutaMathcad = "RUTA_FLUSHEP_MATHCAD"

        Case "IM_SHEAREP_MATHCAD"
            ObtieneNombreRutaMathcad = "RUTA_SHEAREP_MATHCAD"
        
        Case "IM_SHEAREXP_MATHCAD"
            ObtieneNombreRutaMathcad = "RUTA_SHEAREXP_MATHCAD"
        
        Case "IM_SPLICEEP_MATHCAD"
            ObtieneNombreRutaMathcad = "RUTA_SPLICEEP_MATHCAD"
            
        Case "IM_SPLICECP_MATHCAD"
            ObtieneNombreRutaMathcad = "RUTA_SPLICECP_MATHCAD"
            
        Case "IM_BRACING_MATHCAD"
            ObtieneNombreRutaMathcad = "RUTA_BRACING_MATHCAD"
        
        Case "IM_BRACINGEP_MATHCAD"
            ObtieneNombreRutaMathcad = "RUTA_BRACINGEP_MATHCAD"
        
        Case Else
            ObtieneNombreRutaMathcad = ""

    End Select

End Function

Public Sub SeleccionarConexionesMathcad()

    Dim Formulario As SeleccionConexionesExcelEngine
    Dim NombreHoja As String
    Dim NombreTabla As String

    If Not ObtieneDatosTablaMathcad(NombreHoja, NombreTabla) Then Exit Sub

    Set Formulario = New SeleccionConexionesExcelEngine

    Call Formulario.Inicializar(NombreHoja, NombreTabla)
    Formulario.Show

End Sub


Public Function ObtieneDatosTablaMathcad( _
    ByRef NombreHoja As String, _
    ByRef NombreTabla As String) As Boolean

    Dim HojaActual As Worksheet
    Dim TablaActual As ListObject
    Dim TablaEncontrada As ListObject

    If TypeName(ActiveSheet) <> "Worksheet" Then
        MsgBox "La hoja activa no es una hoja de calculo.", vbExclamation
        Exit Function
    End If

    Set HojaActual = ActiveSheet

    For Each TablaActual In HojaActual.ListObjects

        If TablaContieneColumna(TablaActual, "CALCULAR") And _
           TablaContieneColumna(TablaActual, "Unicode") Then

            If Not TablaEncontrada Is Nothing Then
                MsgBox "Hay mas de una tabla con las columnas " & _
                       "CALCULAR y Unicode.", vbExclamation
                Exit Function
            End If

            Set TablaEncontrada = TablaActual

        End If

    Next TablaActual

    If TablaEncontrada Is Nothing Then
        MsgBox "No se ha encontrado una tabla con las columnas " & _
               "CALCULAR y Unicode en la hoja activa.", vbExclamation
        Exit Function
    End If

    NombreHoja = HojaActual.Name
    NombreTabla = TablaEncontrada.Name
    ObtieneDatosTablaMathcad = True

End Function

Private Function IndiceColumna( _
    ByVal Tabla As ListObject, _
    ByVal NombreColumna As String) As Long

    Dim Columna As ListColumn

    IndiceColumna = 0

    If Tabla Is Nothing Then Exit Function

    For Each Columna In Tabla.ListColumns
        If StrComp( _
            Trim$(Columna.Name), _
            Trim$(NombreColumna), _
            vbTextCompare) = 0 Then

            IndiceColumna = Columna.Index
            Exit Function
        End If
    Next Columna

End Function


Private Function TablaContieneColumna( _
    ByVal Tabla As ListObject, _
    ByVal NombreColumna As String) As Boolean

    TablaContieneColumna = (IndiceColumna(Tabla, NombreColumna) > 0)

End Function


Private Function ObtieneRangoNombreLibro( _
    ByVal NombreDefinido As String) As Range

    Dim NombreLibro As Name

    On Error Resume Next
    Set NombreLibro = ThisWorkbook.Names(NombreDefinido)

    If Not NombreLibro Is Nothing Then
        Set ObtieneRangoNombreLibro = NombreLibro.RefersToRange
    End If

    On Error GoTo 0

End Function


Private Function CarpetaExiste(ByVal RutaCarpeta As String) As Boolean

    Dim SistemaArchivos As Object

    Set SistemaArchivos = CreateObject("Scripting.FileSystemObject")
    CarpetaExiste = SistemaArchivos.FolderExists(RutaCarpeta)

End Function


-------------------------------------------------------------------------------
VBA MACRO Hoja15.cls 