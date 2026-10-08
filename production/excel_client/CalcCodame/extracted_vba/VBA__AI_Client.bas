- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Option Explicit

' ============================================================================
' Cliente de Excel <-> Servidor de Inferencia (Trabaja directamente en ActiveSheet)
' ============================================================================

' --- Configuración: EDITAR AQUÍ --------------------------------------------------------
Private Const SERVER_URL As String = "http://10.97.116.84:8080"   ' URL y puerto del servidor
Private Const API_KEY As String = "changeme"                     ' Clave de seguridad (AI_API_KEY)
Private Const HEADER_ROW As Long = 1                             ' Fila de cabecera para rangos simples
Private Const FIRST_DATA_ROW As Long = 2                         ' Fila inicial de datos para rangos simples
Private Const STATUS_COLUMN_NAME As String = "Estado_IA"        ' Columna de seguimiento
Private Const TIMEOUT_MS As Long = 30000                         ' Timeout HTTP (30s)
' ----------------------------------------------------------------------------------------

Private Const STATUS_PREDICHO As String = "Predicho"
Private Const STATUS_VALIDADO As String = "Validado y enviado"


' ============================================================================
' BOTÓN 1: "Enviar a IA"
' ============================================================================
Public Sub SendToAI()
    Dim payload As String
    Dim response As String
    Dim httpStatus As Long
    Dim totalRows As Long

    On Error GoTo ErrHandler

    payload = BuildCombinedJson(onlyStatusPredicho:=False, outCount:=totalRows)

    If totalRows = 0 Then
        MsgBox "No se encontraron filas con datos válidos en la hoja activa ('" & ActiveSheet.Name & "').", vbExclamation
        Exit Sub
    End If

    Application.StatusBar = "Enviando " & totalRows & " unión(es) a la IA..."
    If Not HttpPostJson(SERVER_URL & "/predict", payload, response, httpStatus) Then
        MsgBox "No se ha podido contactar con el servidor de IA:" & vbCrLf & response, vbCritical
        GoTo CleanExit
    End If

    If httpStatus <> 200 Then
        MsgBox "El servidor devolvió un error (HTTP " & httpStatus & "):" & vbCrLf & response, vbCritical
        GoTo CleanExit
    End If

    WriteResponseToSheet response, STATUS_PREDICHO
    MsgBox "Predicción recibida para " & totalRows & " fila(s).", vbInformation

CleanExit:
    Application.StatusBar = False
    Exit Sub

ErrHandler:
    Application.StatusBar = False
    MsgBox "Error inesperado en SendToAI: " & Err.Description, vbCritical
End Sub


' ============================================================================
' BOTÓN 2: "Validar y enviar"
' ============================================================================
Public Sub ValidateAndSend()
    Dim payload As String
    Dim response As String
    Dim httpStatus As Long
    Dim totalRows As Long

    On Error GoTo ErrHandler

    payload = BuildCombinedJson(onlyStatusPredicho:=True, outCount:=totalRows)

    If totalRows = 0 Then
        MsgBox "No hay filas en estado '" & STATUS_PREDICHO & "' para validar." & vbCrLf & _
               "Pulsa primero 'Enviar a IA', revisa/edita los valores y vuelve a intentarlo.", vbExclamation
        Exit Sub
    End If

    Application.StatusBar = "Enviando " & totalRows & " fila(s) validada(s)..."
    If Not HttpPostJson(SERVER_URL & "/validate", payload, response, httpStatus) Then
        MsgBox "No se ha podido contactar con el servidor de IA:" & vbCrLf & response, vbCritical
        GoTo CleanExit
    End If

    If httpStatus <> 200 Then
        MsgBox "El servidor devolvió un error (HTTP " & httpStatus & "):" & vbCrLf & response, vbCritical
        GoTo CleanExit
    End If

    UpdateStatusForSentRows STATUS_VALIDADO & " (" & Format(Now, "yyyy-mm-dd hh:nn") & ")"
    MsgBox totalRows & " fila(s) validada(s) y guardada(s) en el servidor.", vbInformation

CleanExit:
    Application.StatusBar = False
    Exit Sub

ErrHandler:
    Application.StatusBar = False
    MsgBox "Error inesperado en ValidateAndSend: " & Err.Description, vbCritical
End Sub


' ============================================================================
' BOTÓN 3: "Reentrenar Modelo"
' ============================================================================
Public Sub ForceRetrain()
    Dim response As String
    Dim httpStatus As Long

    If MsgBox("¿Deseas iniciar el reentrenamiento del modelo en el servidor con los datos actuales?", _
              vbQuestion + vbYesNo, "Confirmar reentrenamiento") = vbNo Then
        Exit Sub
    End If

    Application.StatusBar = "Solicitando reentrenamiento del modelo..."
    
    If Not HttpPostJson(SERVER_URL & "/retrain", "{}", response, httpStatus) Then
        MsgBox "No se ha podido contactar con el servidor:" & vbCrLf & response, vbCritical
        GoTo CleanExit
    End If

    If httpStatus <> 200 Then
        MsgBox "El servidor devolvió un error (HTTP " & httpStatus & "):" & vbCrLf & response, vbCritical
        GoTo CleanExit
    End If

    MsgBox "El reentrenamiento se ha iniciado con éxito en segundo plano." & vbCrLf & _
           "El servidor actualizará automáticamente los pesos al terminar.", vbInformation

CleanExit:
    Application.StatusBar = False
End Sub


' ============================================================================
' LÓGICA DE LECTURA Y CONSTRUCCIÓN DE JSON
' ============================================================================
Private Function IsListRowEmpty(lo As ListObject, rowIdx As Long) As Boolean
    Dim c As Long
    For c = 1 To lo.ListColumns.Count
        If Trim$(CStr(lo.DataBodyRange.Cells(rowIdx, c).value)) <> "" Then
            IsListRowEmpty = False
            Exit Function
        End If
    Next c
    IsListRowEmpty = True
End Function

Private Function IsSheetRowEmpty(ws As Worksheet, rowIdx As Long, lastCol As Long) As Boolean
    Dim c As Long
    For c = 1 To lastCol
        If Trim$(CStr(ws.Cells(rowIdx, c).value)) <> "" Then
            IsSheetRowEmpty = False
            Exit Function
        End If
    Next c
    IsSheetRowEmpty = True
End Function

Private Function BuildCombinedJson(onlyStatusPredicho As Boolean, ByRef outCount As Long) As String
    Dim lo1 As ListObject, lo2 As ListObject, loPred As ListObject
    Dim dictM1 As Object, dictAux As Object
    Dim r As Long, c As Long
    Dim unicodeKey As String, keyLookup As String
    Dim jsonRow As String, payload As String
    Dim colName As String, statusVal As String
    Dim statusColIdxPred As Long, unicodeColIdx1 As Long, unicodeColIdx2 As Long, unicodeColIdxPred As Long
    Dim rowDict As Object, auxRow As Object, mergedRow As Object
    Dim k As Variant, firstVal As Boolean
    Dim auxKey As String

    outCount = 0
    Set lo1 = FindListObject("Tabla_MOMENT_M1")
    Set lo2 = FindListObject("TParametrosAux")
    Set loPred = FindListObject("Tabla_Predicciones_IA")

    ' 1. Indexar TParametrosAux: por FILA DE HOJA (no necesita UNICODE) y, si la tabla lo tiene, por UNICODE
    Set dictAux = CreateObject("Scripting.Dictionary")
    If Not lo2 Is Nothing Then
        unicodeColIdx2 = GetListColumnIndex(lo2, "UNICODE")
        For r = 1 To lo2.ListRows.Count
            If Not IsListRowEmpty(lo2, r) Then
                Set auxRow = CreateObject("Scripting.Dictionary")
                For c = 1 To lo2.ListColumns.Count
                    colName = lo2.HeaderRowRange.Cells(1, c).value
                    If UCase$(colName) <> "UNICODE" Then
                        auxRow(colName) = CellToJsonValue(lo2.DataBodyRange.Cells(r, c))
                    End If
                Next c

                auxKey = "@ROW" & CStr(lo2.DataBodyRange.Cells(r, 1).Row)
                If Not dictAux.Exists(auxKey) Then dictAux.Add auxKey, auxRow

                If unicodeColIdx2 > 0 Then
                    unicodeKey = Trim$(CStr(lo2.DataBodyRange.Cells(r, unicodeColIdx2).value))
                    If unicodeKey <> "" Then
                        If Not dictAux.Exists(unicodeKey) Then dictAux.Add unicodeKey, auxRow
                    End If
                End If
            End If
        Next r
    End If

    ' 2. Indexar Tabla_MOMENT_M1 (cada fila ya lleva fusionados los parametros de TParametrosAux)
    Set dictM1 = CreateObject("Scripting.Dictionary")
    If Not lo1 Is Nothing Then
        unicodeColIdx1 = GetListColumnIndex(lo1, "UNICODE")
        For r = 1 To lo1.ListRows.Count
            If Not IsListRowEmpty(lo1, r) Then
                unicodeKey = ""
                If unicodeColIdx1 > 0 Then unicodeKey = Trim$(CStr(lo1.DataBodyRange.Cells(r, unicodeColIdx1).value))
                keyLookup = IIf(unicodeKey <> "", unicodeKey, "ROW_" & CStr(r))

                If Not dictM1.Exists(keyLookup) Then
                    Set rowDict = CreateObject("Scripting.Dictionary")
                    For c = 1 To lo1.ListColumns.Count
                        colName = lo1.HeaderRowRange.Cells(1, c).value
                        rowDict(colName) = CellToJsonValue(lo1.DataBodyRange.Cells(r, c))
                    Next c

                    Set auxRow = FindAuxRow(dictAux, lo1.DataBodyRange.Cells(r, 1).Row, unicodeKey)
                    If Not auxRow Is Nothing Then
                        For Each k In auxRow.Keys
                            If Not rowDict.Exists(CStr(k)) Then
                                rowDict(CStr(k)) = auxRow(k)
                            ElseIf rowDict(CStr(k)) = "null" Then
                                rowDict(CStr(k)) = auxRow(k)
                            End If
                        Next k
                    End If

                    dictM1.Add keyLookup, rowDict
                End If
            End If
        Next r
    End If

    ' ------------------------------------------------------------------------
    ' CASO A: VALIDACIÓN (onlyStatusPredicho = True) usando Tabla_Predicciones_IA
    ' ------------------------------------------------------------------------
    If onlyStatusPredicho Then
        If loPred Is Nothing Then
            BuildCombinedJson = BuildActiveSheetJson(True, outCount)
            Exit Function
        End If

        statusColIdxPred = GetListColumnIndex(loPred, STATUS_COLUMN_NAME)
        unicodeColIdxPred = GetListColumnIndex(loPred, "UNICODE")

        payload = "{""rows"": ["

        For r = 1 To loPred.ListRows.Count
            If Not IsListRowEmpty(loPred, r) Then
                statusVal = ""
                If statusColIdxPred > 0 Then
                    statusVal = Trim$(CStr(loPred.DataBodyRange.Cells(r, statusColIdxPred).value))
                End If

                If UCase$(Left$(statusVal, Len(STATUS_PREDICHO))) = UCase$(STATUS_PREDICHO) Then
                    unicodeKey = ""
                    If unicodeColIdxPred > 0 Then unicodeKey = Trim$(CStr(loPred.DataBodyRange.Cells(r, unicodeColIdxPred).value))
                    keyLookup = IIf(unicodeKey <> "", unicodeKey, "ROW_" & CStr(r))

                    Set mergedRow = CreateObject("Scripting.Dictionary")

                    ' Fusionar MOMENT_M1
                    If dictM1.Exists(keyLookup) Then
                        Set rowDict = dictM1(keyLookup)
                        For Each k In rowDict.Keys
                            mergedRow(CStr(k)) = rowDict(k)
                        Next k
                    End If

                    ' Fusionar Aux
                    If unicodeKey <> "" And dictAux.Exists(unicodeKey) Then
                        Set auxRow = dictAux(unicodeKey)
                        For Each k In auxRow.Keys
                            mergedRow(CStr(k)) = auxRow(k)
                        Next k
                    End If

                    ' Fusionar Tabla_Predicciones_IA (incluye cambios manuales)
                    For c = 1 To loPred.ListColumns.Count
                        colName = loPred.HeaderRowRange.Cells(1, c).value
                        If UCase$(colName) <> UCase$(STATUS_COLUMN_NAME) Then
                            mergedRow(colName) = CellToJsonValue(loPred.DataBodyRange.Cells(r, c))
                        End If
                    Next c

                    ' Construir JSON
                    If outCount > 0 Then payload = payload & ","
                    jsonRow = "{"
                    firstVal = True
                    For Each k In mergedRow.Keys
                        If Not firstVal Then jsonRow = jsonRow & ","
                        jsonRow = jsonRow & JsonString(CStr(k)) & ":" & mergedRow(k)
                        firstVal = False
                    Next k
                    jsonRow = jsonRow & "}"

                    payload = payload & jsonRow
                    outCount = outCount + 1
                End If
            End If
        Next r

        payload = payload & "]}"
        BuildCombinedJson = payload
        Exit Function
    End If

    ' ------------------------------------------------------------------------
    ' CASO B: PREDICCIÓN INICIAL (onlyStatusPredicho = False) desde MOMENT_M1
    ' ------------------------------------------------------------------------
    If Not lo1 Is Nothing Then
        unicodeColIdx1 = GetListColumnIndex(lo1, "UNICODE")
        payload = "{""rows"": ["

        For r = 1 To lo1.ListRows.Count
            If Not IsListRowEmpty(lo1, r) Then
                unicodeKey = ""
                If unicodeColIdx1 > 0 Then unicodeKey = Trim$(CStr(lo1.DataBodyRange.Cells(r, unicodeColIdx1).value))
                keyLookup = IIf(unicodeKey <> "", unicodeKey, "ROW_" & CStr(r))

                If outCount > 0 Then payload = payload & ","
                jsonRow = "{"

                ' MOMENT_M1
                For c = 1 To lo1.ListColumns.Count
                    colName = lo1.HeaderRowRange.Cells(1, c).value
                    If c > 1 Then jsonRow = jsonRow & ","
                    jsonRow = jsonRow & JsonString(colName) & ":" & CellToJsonValue(lo1.DataBodyRange.Cells(r, c))
                Next c

                ' Aux (misma fila de hoja que la fila de MOMENT_M1, o por UNICODE si la tabla lo tiene)
                Set auxRow = FindAuxRow(dictAux, lo1.DataBodyRange.Cells(r, 1).Row, unicodeKey)
                If Not auxRow Is Nothing Then
                    For Each k In auxRow.Keys
                        If GetListColumnIndex(lo1, CStr(k)) = 0 Then
                            jsonRow = jsonRow & "," & JsonString(CStr(k)) & ":" & auxRow(k)
                        End If
                    Next k
                End If

                jsonRow = jsonRow & "}"
                payload = payload & jsonRow
                outCount = outCount + 1
            End If
        Next r

        payload = payload & "]}"
        BuildCombinedJson = payload
        Exit Function
    End If

    ' Fallback en Rango de Hoja Activa
    BuildCombinedJson = BuildActiveSheetJson(onlyStatusPredicho, outCount)
End Function

Private Function BuildActiveSheetJson(onlyStatusPredicho As Boolean, ByRef outCount As Long) As String
    Dim ws As Worksheet
    Dim lastRow As Long, lastCol As Long
    Dim headers() As String
    Dim statusCol As Long, r As Long
    Dim payload As String

    Set ws = ActiveSheet
    lastCol = GetLastColumn(ws)
    lastRow = GetLastRow(ws)
    headers = ReadHeaders(ws, lastCol)
    statusCol = FindColumn(headers, STATUS_COLUMN_NAME)

    outCount = 0
    payload = "{""rows"": ["
    For r = FIRST_DATA_ROW To lastRow
        If IsSheetRowEmpty(ws, r, lastCol) Then GoTo NextR

        If onlyStatusPredicho Then
            If statusCol = 0 Or UCase$(Left$(Trim$(CStr(ws.Cells(r, statusCol).value)), Len(STATUS_PREDICHO))) <> UCase$(STATUS_PREDICHO) Then GoTo NextR
        End If
        If outCount > 0 Then payload = payload & ","
        payload = payload & RowToJson(ws, headers, r)
        outCount = outCount + 1
NextR:
    Next r
    payload = payload & "]}"
    BuildActiveSheetJson = payload
End Function


' ============================================================================
' ESCRITURA DE RESULTADOS Y ESTADO DE IA
' ============================================================================
Private Sub WriteResponseToSheet(ByVal jsonResponse As String, ByVal newStatus As String)
    Dim rowsArr As Collection
    Dim rowObj As Object
    Dim loAux As ListObject
    Dim loMoment As ListObject
    Dim loPred As ListObject
    Dim statusColumn As ListColumn
    Dim i As Long
    Dim targetRow As Long
    Dim value As Variant
    Dim p1 As Double
    Dim d As Double
    Dim tf As Double
    Dim lh As Double
    Dim tensionRows As Long
    Dim previousCalculation As XlCalculation
    Dim previousEnableEvents As Boolean
    Dim previousScreenUpdating As Boolean
    Dim errorNumber As Long
    Dim errorSource As String
    Dim errorDescription As String

    Set rowsArr = JsonParseRowsField(jsonResponse, "rows")
    If rowsArr Is Nothing Then Exit Sub
    If rowsArr.Count = 0 Then Exit Sub

    Set loAux = FindListObject("TParametrosAux")
    Set loMoment = FindListObject("Tabla_MOMENT_M1")

    If loAux Is Nothing Then
        Err.Raise vbObjectError + 2100, "WriteResponseToSheet", _
                  "No se encontro la tabla TParametrosAux."
    End If

    If loMoment Is Nothing Then
        Err.Raise vbObjectError + 2101, "WriteResponseToSheet", _
                  "No se encontro la tabla Tabla_MOMENT_M1."
    End If

    If loAux.DataBodyRange Is Nothing Then
        Err.Raise vbObjectError + 2102, "WriteResponseToSheet", _
                  "TParametrosAux no contiene filas."
    End If

    If loMoment.DataBodyRange Is Nothing Then
        Err.Raise vbObjectError + 2103, "WriteResponseToSheet", _
                  "Tabla_MOMENT_M1 no contiene filas."
    End If

    If rowsArr.Count <> loAux.ListRows.Count Then
        Err.Raise vbObjectError + 2104, "WriteResponseToSheet", _
                  "La respuesta contiene " & rowsArr.Count & _
                  " filas, pero TParametrosAux contiene " & _
                  loAux.ListRows.Count & ". No se ha escrito ningun dato."
    End If

    If rowsArr.Count > loMoment.ListRows.Count Then
        Err.Raise vbObjectError + 2105, "WriteResponseToSheet", _
                  "Tabla_MOMENT_M1 no tiene filas suficientes para la respuesta."
    End If

    Set statusColumn = FindListColumnCI(loMoment, STATUS_COLUMN_NAME)
    If statusColumn Is Nothing Then
        Set statusColumn = loMoment.ListColumns.Add
        statusColumn.Name = STATUS_COLUMN_NAME
    End If

    previousCalculation = Application.Calculation
    previousEnableEvents = Application.EnableEvents
    previousScreenUpdating = Application.ScreenUpdating

    On Error GoTo WriteFailed
    Application.Calculation = xlCalculationManual
    Application.EnableEvents = False
    Application.ScreenUpdating = False

    For i = 1 To rowsArr.Count
        Set rowObj = rowsArr(i)
        targetRow = ResolveMomentRow(loMoment, rowObj, i)

        ' Correspondencias directas de TransformaValoresCodigoCalculo.
        CopyJsonValue rowObj, loMoment, targetRow, "Unicode", "UNICODE", "Unicode"
        CopyJsonValue rowObj, loMoment, targetRow, "Standards", "STANDARDS", "Normativas"
        CopyJsonValue rowObj, loMoment, targetRow, "BEAM", "BEAM", "Beam"
        CopyJsonValue rowObj, loMoment, targetRow, "COLUMN", "COLUMN", "Column"
        CopyJsonValue rowObj, loMoment, targetRow, "MzEd_Porcen", _
                      "Connection Capacity Moment [%]", "Capacity_Moment_Percentage", "MzEd_Porcen"
        CopyJsonValue rowObj, loMoment, targetRow, "FyEd_Porcen", _
                      "Connection Capacity Shear [%]", "Capacity_Shear_Percentage", "FyEd_Porcen"
        CopyJsonValue rowObj, loMoment, targetRow, "FxEd_Porcen", _
                      "Connection Capacity Axial [%]", "Capacity_Axial_Percentage", "FxEd_Porcen"
        CopyJsonValue rowObj, loMoment, targetRow, "Pr_Porcen", "Pr_Porcen"
        CopyJsonValue rowObj, loMoment, targetRow, "MzEd_PanelZone", "MzEd_PanelZone"
        CopyJsonValue rowObj, loMoment, targetRow, "Vgra", "Vgra"
        CopyJsonValue rowObj, loMoment, targetRow, "Havg", "Havg"
        CopyJsonValue rowObj, loMoment, targetRow, "ThicknessName_t_webstiff", "tws"
        CopyJsonValue rowObj, loMoment, targetRow, "Bws", "Bws"
        CopyJsonValue rowObj, loMoment, targetRow, "Lws", "Lws"
        CopyJsonValue rowObj, loMoment, targetRow, "b_ep", "Bp"
        CopyJsonValue rowObj, loMoment, targetRow, "Lp", "Lp"
        CopyJsonValue rowObj, loMoment, targetRow, "dev", "e"
        CopyJsonValue rowObj, loMoment, targetRow, "p12_Outer", "p0"
        CopyJsonValue rowObj, loMoment, targetRow, "BoltName_ep", "Bolt"
        CopyJsonValue rowObj, loMoment, targetRow, "p2_ep", "g"
        CopyJsonValue rowObj, loMoment, targetRow, "pb", "p2"
        CopyJsonValue rowObj, loMoment, targetRow, "p3", "p3"
        CopyJsonValue rowObj, loMoment, targetRow, "p4", "p4"
        CopyJsonValue rowObj, loMoment, targetRow, "p5", "p5"
        CopyJsonValue rowObj, loMoment, targetRow, "p6", "p6"
        CopyJsonValue rowObj, loMoment, targetRow, "p7", "p7"
        CopyJsonValue rowObj, loMoment, targetRow, "p8", "p8"
        CopyJsonValue rowObj, loMoment, targetRow, "p9", "p9"
        CopyJsonValue rowObj, loMoment, targetRow, "p10", "p10"
        CopyJsonValue rowObj, loMoment, targetRow, "p11", "p11"
        CopyJsonValue rowObj, loMoment, targetRow, "p12", "p12"
        CopyJsonValue rowObj, loMoment, targetRow, "wf", "w1"
        CopyJsonValue rowObj, loMoment, targetRow, "ww", "w2"
        CopyJsonValue rowObj, loMoment, targetRow, "w3", "w3"
        CopyJsonValue rowObj, loMoment, targetRow, "w4", "w4"
        CopyJsonValue rowObj, loMoment, targetRow, "wh", "w5"
        CopyJsonValue rowObj, loMoment, targetRow, "BoltGrade", "BOLT STANDARD", "EstandarTornillos"
        CopyJsonValue rowObj, loMoment, targetRow, "Electrode", "WELDING ELECTRODE", "ElectrodoSoldadura"
        CopyJsonValue rowObj, loMoment, targetRow, "yieldmethod", "Yieldmethod", "yieldmethod"
        CopyJsonValue rowObj, loMoment, targetRow, "Source", "SOURCE", "Source"
        CopyJsonValue rowObj, loMoment, targetRow, "Designation", "DESIGNATION", "Designation"

        ' Los espesores de placa se guardan en CODAME como texto, por ejemplo "20mm".
        If TryGetJsonValueCI(rowObj, "tp", value) Then
            SetListValue loMoment, targetRow, "ThicknessName_t_ep", MillimetresText(value)
        End If
        If TryGetJsonValueCI(rowObj, "ts", value) Then
            SetListValue loMoment, targetRow, "ThicknessName_t_compstiff", MillimetresText(value)
        End If
        If TryGetJsonValueCI(rowObj, "tbs", value) Then
            SetListValue loMoment, targetRow, "ThicknessName_t_BeamHcompstiff", MillimetresText(value)
        End If
        If TryGetJsonValueCI(rowObj, "tst", value) Then
            SetListValue loMoment, targetRow, "ThicknessName_t_tenstiff", MillimetresText(value)
        End If

        ' d se transforma en pfo. pfi = p1 - d - espesor del ala de la viga.
        If TryGetJsonDouble(rowObj, "d", d) Then
            SetListValue loMoment, targetRow, "pfo", d
        End If
        If TryGetJsonDouble(rowObj, "p1", p1) And _
           TryGetJsonDouble(rowObj, "d", d) And _
           TryGetAuxDouble(loAux, i, "BEAM_tf_mm", tf) Then
            SetListValue loMoment, targetRow, "pfi", p1 - d - tf
        End If

        ' La presencia de cartela fija estos dos parametros.
        If TryGetJsonDouble(rowObj, "Lh", lh) Then
            SetListValue loMoment, targetRow, "Lh", lh
            If lh <> 0# Then
                SetListValue loMoment, targetRow, "AnguloCantonera", 60#
                SetListValue loMoment, targetRow, "FactorCantoCantonera", 0.7
            Else
                SetListValue loMoment, targetRow, "AnguloCantonera", 0#
                SetListValue loMoment, targetRow, "FactorCantoCantonera", 0#
            End If
        End If

        If TryCalculateTensionRows(rowObj, loAux, i, tensionRows) Then
            SetListValue loMoment, targetRow, "ntensionrows", tensionRows
        End If

        ' Propiedades que en C# se obtienen del material o se fijan como constantes.
        If TryGetAuxValue(loAux, i, "fy_acero_mpa", value) Then
            SetListValue loMoment, targetRow, "fy", value
            SetListValue loMoment, targetRow, "fyp", value
        End If
        If TryGetAuxValue(loAux, i, "fu_acero_mpa", value) Then
            SetListValue loMoment, targetRow, "fu", value
            SetListValue loMoment, targetRow, "fup", value
        End If
        SetListValue loMoment, targetRow, "BoltThreads", "TRUE"
        SetListValue loMoment, targetRow, "WeldFactor", 1#
        SetListValue loMoment, targetRow, "BoltsInTensionFactor", 2#

        statusColumn.DataBodyRange.Cells(targetRow, 1).value = newStatus
    Next i

    ' La tabla complementaria deja de ser necesaria.
    Set loPred = FindListObject("Tabla_Predicciones_IA")
    If Not loPred Is Nothing Then
        loPred.Range.Clear
        loPred.Delete
    End If

WriteFinished:
    Application.Calculation = previousCalculation
    Application.EnableEvents = previousEnableEvents
    Application.ScreenUpdating = previousScreenUpdating

    If errorNumber <> 0 Then
        Err.Raise errorNumber, errorSource, errorDescription
    End If
    Exit Sub

WriteFailed:
    errorNumber = Err.Number
    errorSource = Err.Source
    errorDescription = Err.Description
    Resume WriteFinished
End Sub

Private Sub CopyJsonValue(ByVal rowObj As Object, _
                          ByVal lo As ListObject, _
                          ByVal rowIndex As Long, _
                          ByVal targetHeader As String, _
                          ParamArray sourceHeaders() As Variant)
    Dim sourceHeader As Variant
    Dim value As Variant

    For Each sourceHeader In sourceHeaders
        If TryGetJsonValueCI(rowObj, CStr(sourceHeader), value) Then
            SetListValue lo, rowIndex, targetHeader, value
            Exit Sub
        End If
    Next sourceHeader
End Sub

Private Function TryGetJsonValueCI(ByVal rowObj As Object, _
                                   ByVal keyName As String, _
                                   ByRef value As Variant) As Boolean
    Dim key As Variant

    If rowObj.Exists(keyName) Then
        value = rowObj(keyName)
        TryGetJsonValueCI = True
        Exit Function
    End If

    For Each key In rowObj.Keys
        If StrComp(CStr(key), keyName, vbTextCompare) = 0 Then
            value = rowObj(key)
            TryGetJsonValueCI = True
            Exit Function
        End If
    Next key
End Function

Private Function TryGetJsonDouble(ByVal rowObj As Object, _
                                  ByVal keyName As String, _
                                  ByRef value As Double) As Boolean
    Dim rawValue As Variant

    If Not TryGetJsonValueCI(rowObj, keyName, rawValue) Then Exit Function
    If IsNull(rawValue) Or IsEmpty(rawValue) Then Exit Function
    If Not IsNumeric(rawValue) Then Exit Function

    value = CDbl(rawValue)
    TryGetJsonDouble = True
End Function

Private Function FindListColumnCI(ByVal lo As ListObject, _
                                  ByVal headerName As String) As ListColumn
    Dim column As ListColumn

    For Each column In lo.ListColumns
        If StrComp(column.Name, headerName, vbTextCompare) = 0 Then
            Set FindListColumnCI = column
            Exit Function
        End If
    Next column
End Function

Private Sub SetListValue(ByVal lo As ListObject, _
                         ByVal rowIndex As Long, _
                         ByVal headerName As String, _
                         ByVal value As Variant)
    Dim column As ListColumn

    Set column = FindListColumnCI(lo, headerName)
    If column Is Nothing Then Exit Sub
    column.DataBodyRange.Cells(rowIndex, 1).value = value
End Sub

Private Function ResolveMomentRow(ByVal loMoment As ListObject, _
                                  ByVal rowObj As Object, _
                                  ByVal fallbackRow As Long) As Long
    Dim unicodeColumn As ListColumn
    Dim unicodeValue As Variant
    Dim found As Range

    ResolveMomentRow = fallbackRow
    If Not TryGetJsonValueCI(rowObj, "UNICODE", unicodeValue) Then Exit Function
    If Len(Trim$(CStr(unicodeValue))) = 0 Then Exit Function

    Set unicodeColumn = FindListColumnCI(loMoment, "Unicode")
    If unicodeColumn Is Nothing Then Exit Function

    Set found = unicodeColumn.DataBodyRange.Find( _
                    What:=unicodeValue, _
                    After:=unicodeColumn.DataBodyRange.Cells(unicodeColumn.DataBodyRange.Rows.Count, 1), _
                    LookIn:=xlValues, _
                    LookAt:=xlWhole, _
                    SearchOrder:=xlByRows, _
                    SearchDirection:=xlNext, _
                    MatchCase:=False)

    If Not found Is Nothing Then
        ResolveMomentRow = found.Row - loMoment.DataBodyRange.Row + 1
    End If
End Function

Private Function TryGetAuxValue(ByVal loAux As ListObject, _
                                ByVal rowIndex As Long, _
                                ByVal headerName As String, _
                                ByRef value As Variant) As Boolean
    Dim column As ListColumn

    Set column = FindListColumnCI(loAux, headerName)
    If column Is Nothing Then Exit Function
    value = column.DataBodyRange.Cells(rowIndex, 1).Value2
    TryGetAuxValue = Not IsError(value)
End Function

Private Function TryGetAuxDouble(ByVal loAux As ListObject, _
                                 ByVal rowIndex As Long, _
                                 ByVal headerName As String, _
                                 ByRef value As Double) As Boolean
    Dim rawValue As Variant

    If Not TryGetAuxValue(loAux, rowIndex, headerName, rawValue) Then Exit Function
    If IsNull(rawValue) Or IsEmpty(rawValue) Then Exit Function
    If Not IsNumeric(rawValue) Then Exit Function

    value = CDbl(rawValue)
    TryGetAuxDouble = True
End Function

Private Function MillimetresText(ByVal value As Variant) As String
    Dim text As String

    text = Trim$(CStr(value))
    If LCase$(Right$(text, 2)) = "mm" Then
        MillimetresText = text
    Else
        MillimetresText = text & "mm"
    End If
End Function

Private Function TryCalculateTensionRows(ByVal rowObj As Object, _
                                         ByVal loAux As ListObject, _
                                         ByVal auxRow As Long, _
                                         ByRef result As Long) As Boolean
    Dim beamDepth As Double
    Dim d As Double
    Dim separation As Double
    Dim position As Double
    Dim finish As Double
    Dim rowsInside As Long
    Dim n As Long

    If Not TryGetAuxDouble(loAux, auxRow, "BEAM_d_mm", beamDepth) Then Exit Function
    If Not TryGetJsonDouble(rowObj, "d", d) Then Exit Function
    If Not TryGetJsonDouble(rowObj, "p1", separation) Then Exit Function

    finish = d + beamDepth
    position = 0#

    If position >= d And position <= finish Then rowsInside = rowsInside + 1

    For n = 1 To 12
        If Not TryGetJsonDouble(rowObj, "p" & CStr(n), separation) Then Exit For
        If separation = 0# Then Exit For

        position = position + separation
        If position >= d And position <= finish Then rowsInside = rowsInside + 1
    Next n

    If rowsInside >= 2 Then
        result = 3
    Else
        result = 2
    End If
    TryCalculateTensionRows = True
End Function



Private Sub UpdateStatusForSentRows(newStatus As String)
    Dim loPred As ListObject, lo1 As ListObject
    Dim r As Long, statusColIdx As Long
    Dim ws As Worksheet, lastRow As Long
    Dim headers() As String

    Set loPred = FindListObject("Tabla_Predicciones_IA")
    If Not loPred Is Nothing Then
        statusColIdx = GetListColumnIndex(loPred, STATUS_COLUMN_NAME)
        If statusColIdx > 0 Then
            For r = 1 To loPred.ListRows.Count
                If UCase$(Left$(Trim$(CStr(loPred.DataBodyRange.Cells(r, statusColIdx).value)), Len(STATUS_PREDICHO))) = UCase$(STATUS_PREDICHO) Then
                    loPred.DataBodyRange.Cells(r, statusColIdx).value = newStatus
                End If
            Next r
        End If
    End If

    Set lo1 = FindListObject("Tabla_MOMENT_M1")
    If Not lo1 Is Nothing Then
        statusColIdx = GetListColumnIndex(lo1, STATUS_COLUMN_NAME)
        If statusColIdx > 0 Then
            For r = 1 To lo1.ListRows.Count
                If UCase$(Left$(Trim$(CStr(lo1.DataBodyRange.Cells(r, statusColIdx).value)), Len(STATUS_PREDICHO))) = UCase$(STATUS_PREDICHO) Then
                    lo1.DataBodyRange.Cells(r, statusColIdx).value = newStatus
                End If
            Next r
        End If
    End If

    If loPred Is Nothing And lo1 Is Nothing Then
        Set ws = ActiveSheet
        headers = ReadHeaders(ws, GetLastColumn(ws))
        statusColIdx = FindColumn(headers, STATUS_COLUMN_NAME)
        lastRow = GetLastRow(ws)

        If statusColIdx > 0 Then
            For r = FIRST_DATA_ROW To lastRow
                If UCase$(Left$(Trim$(CStr(ws.Cells(r, statusColIdx).value)), Len(STATUS_PREDICHO))) = UCase$(STATUS_PREDICHO) Then
                    ws.Cells(r, statusColIdx).value = newStatus
                End If
            Next r
        End If
    End If
End Sub


' ============================================================================
' HELPER BUSCADOR DE OBJETOS
' ============================================================================
Private Function FindListObject(tableName As String) As ListObject
    Dim ws As Worksheet, lo As ListObject
    On Error Resume Next
    
    Set lo = ActiveSheet.ListObjects(tableName)
    If Not lo Is Nothing Then
        Set FindListObject = lo
        Exit Function
    End If

    For Each ws In ThisWorkbook.Worksheets
        Set lo = ws.ListObjects(tableName)
        If Not lo Is Nothing Then
            Set FindListObject = lo
            Exit Function
        End If
    Next ws
    On Error GoTo 0
End Function

Private Function FindAuxRow(dictAux As Object, ByVal sheetRow As Long, ByVal unicodeKey As String) As Object
    ' Devuelve la fila de TParametrosAux que esta en la MISMA FILA DE HOJA que la de MOMENT_M1.
    ' Si no hay coincidencia por fila, prueba por UNICODE (solo si TParametrosAux lo tiene).
    Dim rowKey As String
    rowKey = "@ROW" & CStr(sheetRow)
    If dictAux.Exists(rowKey) Then
        Set FindAuxRow = dictAux(rowKey)
    ElseIf unicodeKey <> "" Then
        If dictAux.Exists(unicodeKey) Then Set FindAuxRow = dictAux(unicodeKey)
    End If
End Function

Private Function GetListColumnIndex(lo As ListObject, colName As String) As Long
    On Error Resume Next
    GetListColumnIndex = lo.ListColumns(colName).Index
    On Error GoTo 0
End Function


' ============================================================================
' HTTP (MSXML2.XMLHTTP)
' ============================================================================
Private Function HttpPostJson(url As String, jsonBody As String, ByRef outResponse As String, ByRef outStatus As Long) As Boolean
    Dim http As Object
    On Error GoTo TryServerXMLHTTP

    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "POST", url, False
    http.setRequestHeader "Content-Type", "application/json; charset=utf-8"
    http.setRequestHeader "X-API-Key", API_KEY
    http.send jsonBody

    outStatus = http.Status
    outResponse = http.responseText
    HttpPostJson = True
    Exit Function

TryServerXMLHTTP:
    On Error GoTo Fail
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts TIMEOUT_MS, TIMEOUT_MS, TIMEOUT_MS, TIMEOUT_MS
    http.Open "POST", url, False
    http.setRequestHeader "Content-Type", "application/json; charset=utf-8"
    http.setRequestHeader "X-API-Key", API_KEY
    http.send jsonBody

    outStatus = http.Status
    outResponse = http.responseText
    HttpPostJson = True
    Exit Function

Fail:
    outResponse = "No se pudo conectar con " & url & " -> " & Err.Description & _
                  vbCrLf & "Comprueba que el servidor está arrancado y la URL/puerto son correctos."
    outStatus = 0
    HttpPostJson = False
End Function


' ============================================================================
' LECTURA / ESCRITURA RANGO HOJA ACTIVA
' ============================================================================
Private Function GetFirstColumn(ws As Worksheet) As Long
    Dim c As Long
    For c = 1 To ws.Columns.Count
        If Trim$(CStr(ws.Cells(HEADER_ROW, c).value)) <> "" Then
            GetFirstColumn = c
            Exit Function
        End If
    Next c
    GetFirstColumn = 1
End Function

Private Function GetLastRow(ws As Worksheet) As Long
    Dim firstCol As Long, lastCol As Long, c As Long
    Dim maxRow As Long, currentLastRow As Long
    
    firstCol = GetFirstColumn(ws)
    lastCol = GetLastColumn(ws)
    
    maxRow = HEADER_ROW
    For c = firstCol To lastCol
        If Trim$(CStr(ws.Cells(HEADER_ROW, c).value)) <> "" Then
            currentLastRow = ws.Cells(ws.Rows.Count, c).End(xlUp).Row
            If currentLastRow > maxRow Then maxRow = currentLastRow
        End If
    Next c
    
    GetLastRow = maxRow
End Function

Private Function GetLastColumn(ws As Worksheet) As Long
    GetLastColumn = ws.Cells(HEADER_ROW, ws.Columns.Count).End(xlToLeft).column
End Function

Private Function ReadHeaders(ws As Worksheet, lastCol As Long) As String()
    Dim headers() As String
    Dim c As Long
    ReDim headers(1 To lastCol)
    For c = 1 To lastCol
        headers(c) = CStr(ws.Cells(HEADER_ROW, c).value)
    Next c
    ReadHeaders = headers
End Function

Private Function FindColumn(headers() As String, targetName As String) As Long
    Dim i As Long
    For i = LBound(headers) To UBound(headers)
        If headers(i) = targetName Then
            FindColumn = i
            Exit Function
        End If
    Next i
    FindColumn = 0
End Function

Private Function RowToJson(ws As Worksheet, headers() As String, r As Long) As String
    Dim c As Long
    Dim sb As String
    Dim cell As Range
    sb = "{"
    For c = LBound(headers) To UBound(headers)
        If headers(c) = "" Then GoTo ContinueLoop
        If c > LBound(headers) And sb <> "{" Then sb = sb & ","
        Set cell = ws.Cells(r, c)
        sb = sb & JsonString(headers(c)) & ":" & CellToJsonValue(cell)
ContinueLoop:
    Next c
    sb = sb & "}"
    RowToJson = sb
End Function

Private Function CellToJsonValue(cell As Range) As String
    On Error GoTo ErrVal

    If IsError(cell.value) Then
        CellToJsonValue = "null"
        Exit Function
    End If

    If IsEmpty(cell.value) Or VarType(cell.value) = vbEmpty Then
        CellToJsonValue = "null"
        Exit Function
    End If

    Select Case VarType(cell.value)
        Case vbBoolean
            If cell.value Then
                CellToJsonValue = "true"
            Else
                CellToJsonValue = "false"
            End If
        Case vbByte, vbInteger, vbLong, vbSingle, vbDouble, vbCurrency, vbDecimal
            CellToJsonValue = Replace(CStr(cell.value), ",", ".")
        Case vbString
            If Trim$(cell.value) = "" Then
                CellToJsonValue = "null"
            Else
                CellToJsonValue = JsonString(CStr(cell.value))
            End If
        Case Else
            If IsNumeric(cell.value) Then
                CellToJsonValue = Replace(CStr(cell.value), ",", ".")
            Else
                CellToJsonValue = JsonString(CStr(cell.value))
            End If
    End Select
    Exit Function

ErrVal:
    CellToJsonValue = "null"
End Function


' ============================================================================
' PARSER JSON Y FORMATO
' ============================================================================
Private Function JsonString(s As String) As String
    Dim t As String
    t = s
    t = Replace(t, "\", "\\")
    t = Replace(t, """", "\""")
    t = Replace(t, vbCrLf, "\n")
    t = Replace(t, vbCr, "\n")
    t = Replace(t, vbLf, "\n")
    t = Replace(t, vbTab, "\t")
    JsonString = """" & t & """"
End Function

Private Function JsonParseRowsField(json As String, field As String) As Collection
    Dim result As New Collection
    Dim keyPos As Long, arrStart As Long, arrEnd As Long
    Dim depth As Long, i As Long
    Dim objStart As Long
    Dim inString As Boolean, prevChar As String
    Dim ch As String, c2 As String
    Dim objDepth As Long, j As Long, ch2 As String

    keyPos = InStr(json, """" & field & """")
    If keyPos = 0 Then
        Set JsonParseRowsField = result
        Exit Function
    End If

    arrStart = InStr(keyPos, json, "[")
    If arrStart = 0 Then
        Set JsonParseRowsField = result
        Exit Function
    End If

    depth = 0
    inString = False
    prevChar = ""
    For i = arrStart To Len(json)
        ch = Mid$(json, i, 1)
        If inString Then
            If ch = """" And prevChar <> "\" Then inString = False
        Else
            If ch = """" Then
                inString = True
            ElseIf ch = "[" Then
                depth = depth + 1
            ElseIf ch = "]" Then
                depth = depth - 1
                If depth = 0 Then
                    arrEnd = i
                    Exit For
                End If
            End If
        End If
        prevChar = ch
    Next i

    If arrEnd = 0 Then
        Set JsonParseRowsField = result
        Exit Function
    End If

    i = arrStart + 1
    Do While i < arrEnd
        c2 = Mid$(json, i, 1)
        If c2 = "{" Then
            objStart = i
            objDepth = 0
            inString = False
            prevChar = ""
            For j = objStart To arrEnd
                ch2 = Mid$(json, j, 1)
                If inString Then
                    If ch2 = """" And prevChar <> "\" Then inString = False
                Else
                    If ch2 = """" Then
                        inString = True
                    ElseIf ch2 = "{" Then
                        objDepth = objDepth + 1
                    ElseIf ch2 = "}" Then
                        objDepth = objDepth - 1
                        If objDepth = 0 Then Exit For
                    End If
                End If
                prevChar = ch2
            Next j

            If j <= arrEnd Then
                result.Add JsonParseObject(Mid$(json, objStart, j - objStart + 1))
                i = j + 1
            Else
                Exit Do
            End If
        Else
            i = i + 1
        End If
    Loop

    Set JsonParseRowsField = result
End Function

Private Function JsonParseObject(s As String) As Object
    Dim dict As Object
    Dim i As Long, n As Long
    Dim inString As Boolean, prevChar As String
    Dim key As String, val As String
    Dim state As Integer
    Dim ch As String

    Set dict = CreateObject("Scripting.Dictionary")
    n = Len(s)
    i = 2

    Do While i < n
        ch = Mid$(s, i, 1)
        Select Case state
            Case 0
                If ch = """" Then
                    state = 1
                    key = ""
                    i = i + 1
                Else
                    i = i + 1
                End If

            Case 1
                If ch = """" Then
                    state = 2
                ElseIf ch = "\" Then
                    If i < n Then
                        key = key & Mid$(s, i + 1, 1)
                        i = i + 1
                    End If
                Else
                    key = key & ch
                End If
                i = i + 1

            Case 2
                If ch = ":" Then
                    i = i + 1
                    Do While i <= n And (Mid$(s, i, 1) = " " Or Mid$(s, i, 1) = vbTab)
                        i = i + 1
                    Loop
                    If i <= n And Mid$(s, i, 1) = """" Then
                        state = 3
                        val = ""
                        i = i + 1
                    Else
                        state = 4
                        val = ""
                    End If
                Else
                    i = i + 1
                End If

            Case 3
                If ch = """" Then
                    dict.Add key, UnescapeJson(val)
                    state = 0
                    i = i + 1
                    Do While i <= n And (Mid$(s, i, 1) = "," Or Mid$(s, i, 1) = " " Or Mid$(s, i, 1) = vbTab)
                        i = i + 1
                    Loop
                ElseIf ch = "\" Then
                    If i < n Then
                        val = val & ch & Mid$(s, i + 1, 1)
                        i = i + 2
                    Else
                        i = i + 1
                    End If
                Else
                    val = val & ch
                    i = i + 1
                End If

            Case 4
                If ch = "," Or ch = "}" Then
                    dict.Add key, ParseJsonLiteral(Trim$(val))
                    state = 0
                    If ch = "," Then i = i + 1
                Else
                    val = val & ch
                    i = i + 1
                End If
        End Select
    Loop

    Set JsonParseObject = dict
End Function

Private Function ParseJsonLiteral(s As String) As Variant
    If s = "null" Or s = "" Then
        ParseJsonLiteral = ""
    ElseIf s = "true" Then
        ParseJsonLiteral = True
    ElseIf s = "false" Then
        ParseJsonLiteral = False
    ElseIf IsNumeric(s) Then
        ParseJsonLiteral = CDbl(s)
    Else
        ParseJsonLiteral = s
    End If
End Function

Private Function UnescapeJson(s As String) As String
    Dim t As String
    t = s
    t = Replace(t, "\n", vbCrLf)
    t = Replace(t, "\t", vbTab)
    t = Replace(t, "\""", """")
    t = Replace(t, "\\", "\")
    UnescapeJson = t
End Function

-------------------------------------------------------------------------------
VBA MACRO VBA_P-code.txt 