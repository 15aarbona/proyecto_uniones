Option Explicit

' ============================================================================
' Cliente de Excel <-> Servidor de Inferencia (Trabaja directamente en ActiveSheet)
' ============================================================================

' --- Configuración: EDITAR AQUÍ --------------------------------------------------------
Private Const SERVER_URL As String = "http://127.0.0.1:8080"   ' URL y puerto del servidor
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
        If Trim$(CStr(lo.DataBodyRange.Cells(rowIdx, c).Value)) <> "" Then
            IsListRowEmpty = False
            Exit Function
        End If
    Next c
    IsListRowEmpty = True
End Function

Private Function IsSheetRowEmpty(ws As Worksheet, rowIdx As Long, lastCol As Long) As Boolean
    Dim c As Long
    For c = 1 To lastCol
        If Trim$(CStr(ws.Cells(rowIdx, c).Value)) <> "" Then
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

    outCount = 0
    Set lo1 = FindListObject("Tabla_MOMENT_M1")
    Set lo2 = FindListObject("TParametrosAux")
    Set loPred = FindListObject("Tabla_Predicciones_IA")

    ' 1. Indexar Tabla_MOMENT_M1
    Set dictM1 = CreateObject("Scripting.Dictionary")
    If Not lo1 Is Nothing Then
        unicodeColIdx1 = GetListColumnIndex(lo1, "UNICODE")
        For r = 1 To lo1.ListRows.Count
            If Not IsListRowEmpty(lo1, r) Then
                unicodeKey = ""
                If unicodeColIdx1 > 0 Then unicodeKey = Trim$(CStr(lo1.DataBodyRange.Cells(r, unicodeColIdx1).Value))
                keyLookup = IIf(unicodeKey <> "", unicodeKey, "ROW_" & CStr(r))

                If Not dictM1.Exists(keyLookup) Then
                    Set rowDict = CreateObject("Scripting.Dictionary")
                    For c = 1 To lo1.ListColumns.Count
                        colName = lo1.HeaderRowRange.Cells(1, c).Value
                        rowDict.Add colName, CellToJsonValue(lo1.DataBodyRange.Cells(r, c))
                    Next c
                    dictM1.Add keyLookup, rowDict
                End If
            End If
        Next r
    End If

    ' 2. Indexar TParametrosAux
    Set dictAux = CreateObject("Scripting.Dictionary")
    If Not lo2 Is Nothing Then
        unicodeColIdx2 = GetListColumnIndex(lo2, "UNICODE")
        For r = 1 To lo2.ListRows.Count
            If Not IsListRowEmpty(lo2, r) Then
                unicodeKey = ""
                If unicodeColIdx2 > 0 Then unicodeKey = Trim$(CStr(lo2.DataBodyRange.Cells(r, unicodeColIdx2).Value))
                If unicodeKey <> "" And Not dictAux.Exists(unicodeKey) Then
                    Set auxRow = CreateObject("Scripting.Dictionary")
                    For c = 1 To lo2.ListColumns.Count
                        colName = lo2.HeaderRowRange.Cells(1, c).Value
                        If colName <> "UNICODE" Then
                            auxRow.Add colName, CellToJsonValue(lo2.DataBodyRange.Cells(r, c))
                        End If
                    Next c
                    dictAux.Add unicodeKey, auxRow
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
                    statusVal = Trim$(CStr(loPred.DataBodyRange.Cells(r, statusColIdxPred).Value))
                End If

                If UCase$(Left$(statusVal, Len(STATUS_PREDICHO))) = UCase$(STATUS_PREDICHO) Then
                    unicodeKey = ""
                    If unicodeColIdxPred > 0 Then unicodeKey = Trim$(CStr(loPred.DataBodyRange.Cells(r, unicodeColIdxPred).Value))
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
                        colName = loPred.HeaderRowRange.Cells(1, c).Value
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
                If unicodeColIdx1 > 0 Then unicodeKey = Trim$(CStr(lo1.DataBodyRange.Cells(r, unicodeColIdx1).Value))
                keyLookup = IIf(unicodeKey <> "", unicodeKey, "ROW_" & CStr(r))

                If outCount > 0 Then payload = payload & ","
                jsonRow = "{"

                ' MOMENT_M1
                For c = 1 To lo1.ListColumns.Count
                    colName = lo1.HeaderRowRange.Cells(1, c).Value
                    If c > 1 Then jsonRow = jsonRow & ","
                    jsonRow = jsonRow & JsonString(colName) & ":" & CellToJsonValue(lo1.DataBodyRange.Cells(r, c))
                Next c

                ' Aux
                If unicodeKey <> "" And dictAux.Exists(unicodeKey) Then
                    Set auxRow = dictAux(unicodeKey)
                    For Each k In auxRow.Keys
                        jsonRow = jsonRow & "," & JsonString(CStr(k)) & ":" & auxRow(k)
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
            If statusCol = 0 Or UCase$(Left$(Trim$(CStr(ws.Cells(r, statusCol).Value)), Len(STATUS_PREDICHO))) <> UCase$(STATUS_PREDICHO) Then GoTo NextR
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
Private Sub WriteResponseToSheet(jsonResponse As String, newStatus As String)
    Dim rowsArr As Collection
    Dim rowObj As Object
    Dim loAux As ListObject, loPred As ListObject
    Dim ws As Worksheet
    Dim startCol As Long, startRow As Long
    Dim i As Long, c As Long
    Dim keysCol As Collection, key As Variant
    Dim numRows As Long, numCols As Long
    Dim targetRange As Range
    Dim hasStatusKey As Boolean

    Set rowsArr = JsonParseRowsField(jsonResponse, "rows")
    If rowsArr.Count = 0 Then Exit Sub

    Set loAux = FindListObject("TParametrosAux")

    If Not loAux Is Nothing Then
        Set ws = loAux.Parent
        startRow = loAux.Range.Row
        startCol = loAux.Range.Column + loAux.Range.Columns.Count + 1

        Set keysCol = New Collection
        Set rowObj = rowsArr(1)
        For Each key In rowObj.Keys
            keysCol.Add CStr(key)
        Next key
        
        hasStatusKey = False
        For Each key In keysCol
            If UCase$(CStr(key)) = UCase$(STATUS_COLUMN_NAME) Then hasStatusKey = True
        Next key
        If Not hasStatusKey Then keysCol.Add STATUS_COLUMN_NAME

        numCols = keysCol.Count
        numRows = rowsArr.Count

        ' Limpiar tabla previa si existía
        Set loPred = FindListObject("Tabla_Predicciones_IA")
        If Not loPred Is Nothing Then
            On Error Resume Next
            loPred.Range.Clear
            loPred.Delete
            On Error GoTo 0
        End If

        ' Cabeceras
        For c = 1 To numCols
            ws.Cells(startRow, startCol + c - 1).Value = keysCol(c)
        Next c

        ' Datos
        For i = 1 To numRows
            Set rowObj = rowsArr(i)
            For c = 1 To numCols
                key = keysCol(c)
                If UCase$(CStr(key)) = UCase$(STATUS_COLUMN_NAME) Then
                    ws.Cells(startRow + i, startCol + c - 1).Value = newStatus
                ElseIf rowObj.Exists(key) Then
                    ws.Cells(startRow + i, startCol + c - 1).Value = rowObj(key)
                End If
            Next c
        Next i

        ' Crear Tabla Estructurada y Centrar Contenido
        Set targetRange = ws.Range(ws.Cells(startRow, startCol), ws.Cells(startRow + numRows, startCol + numCols - 1))
        Set loPred = ws.ListObjects.Add(xlSrcRange, targetRange, , xlYes)
        loPred.Name = "Tabla_Predicciones_IA"
        loPred.Range.HorizontalAlignment = xlCenter ' <-- Texto centrado en toda la tabla
        Exit Sub
    End If

    ' Fallback en Rango
    Set ws = ActiveSheet
    Dim lastCol As Long, lastRow As Long, headers() As String, statusCol As Long
    lastCol = GetLastColumn(ws)
    headers = ReadHeaders(ws, lastCol)

    statusCol = FindColumn(headers, STATUS_COLUMN_NAME)
    If statusCol = 0 Then
        lastCol = lastCol + 1
        ws.Cells(HEADER_ROW, lastCol).Value = STATUS_COLUMN_NAME
        ReDim Preserve headers(1 To lastCol)
        headers(lastCol) = STATUS_COLUMN_NAME
        statusCol = lastCol
    End If

    i = 1
    For lastRow = FIRST_DATA_ROW To GetLastRow(ws)
        If IsSheetRowEmpty(ws, lastRow, GetLastColumn(ws)) Then GoTo NextRWrite
        If i > rowsArr.Count Then Exit For
        Set rowObj = rowsArr(i)
        For Each key In rowObj.Keys
            statusCol = FindColumn(headers, CStr(key))
            If statusCol = 0 Then
                lastCol = GetLastColumn(ws) + 1
                ws.Cells(HEADER_ROW, lastCol).Value = CStr(key)
                ReDim Preserve headers(1 To lastCol)
                headers(lastCol) = CStr(key)
                statusCol = lastCol
            End If
            ws.Cells(lastRow, statusCol).Value = rowObj(key)
        Next key
        statusCol = FindColumn(headers, STATUS_COLUMN_NAME)
        ws.Cells(lastRow, statusCol).Value = newStatus
        i = i + 1
NextRWrite:
    Next lastRow
End Sub

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
                If UCase$(Left$(Trim$(CStr(loPred.DataBodyRange.Cells(r, statusColIdx).Value)), Len(STATUS_PREDICHO))) = UCase$(STATUS_PREDICHO) Then
                    loPred.DataBodyRange.Cells(r, statusColIdx).Value = newStatus
                End If
            Next r
        End If
    End If

    Set lo1 = FindListObject("Tabla_MOMENT_M1")
    If Not lo1 Is Nothing Then
        statusColIdx = GetListColumnIndex(lo1, STATUS_COLUMN_NAME)
        If statusColIdx > 0 Then
            For r = 1 To lo1.ListRows.Count
                If UCase$(Left$(Trim$(CStr(lo1.DataBodyRange.Cells(r, statusColIdx).Value)), Len(STATUS_PREDICHO))) = UCase$(STATUS_PREDICHO) Then
                    lo1.DataBodyRange.Cells(r, statusColIdx).Value = newStatus
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
                If UCase$(Left$(Trim$(CStr(ws.Cells(r, statusColIdx).Value)), Len(STATUS_PREDICHO))) = UCase$(STATUS_PREDICHO) Then
                    ws.Cells(r, statusColIdx).Value = newStatus
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
        If Trim$(CStr(ws.Cells(HEADER_ROW, c).Value)) <> "" Then
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
        If Trim$(CStr(ws.Cells(HEADER_ROW, c).Value)) <> "" Then
            currentLastRow = ws.Cells(ws.Rows.Count, c).End(xlUp).Row
            If currentLastRow > maxRow Then maxRow = currentLastRow
        End If
    Next c
    
    GetLastRow = maxRow
End Function

Private Function GetLastColumn(ws As Worksheet) As Long
    GetLastColumn = ws.Cells(HEADER_ROW, ws.Columns.Count).End(xlToLeft).Column
End Function

Private Function ReadHeaders(ws As Worksheet, lastCol As Long) As String()
    Dim headers() As String
    Dim c As Long
    ReDim headers(1 To lastCol)
    For c = 1 To lastCol
        headers(c) = CStr(ws.Cells(HEADER_ROW, c).Value)
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

    If IsError(cell.Value) Then
        CellToJsonValue = "null"
        Exit Function
    End If

    If IsEmpty(cell.Value) Or VarType(cell.Value) = vbEmpty Then
        CellToJsonValue = "null"
        Exit Function
    End If

    Select Case VarType(cell.Value)
        Case vbBoolean
            If cell.Value Then
                CellToJsonValue = "true"
            Else
                CellToJsonValue = "false"
            End If
        Case vbByte, vbInteger, vbLong, vbSingle, vbDouble, vbCurrency, vbDecimal
            CellToJsonValue = Replace(CStr(cell.Value), ",", ".")
        Case vbString
            If Trim$(cell.Value) = "" Then
                CellToJsonValue = "null"
            Else
                CellToJsonValue = JsonString(CStr(cell.Value))
            End If
        Case Else
            If IsNumeric(cell.Value) Then
                CellToJsonValue = Replace(CStr(cell.Value), ",", ".")
            Else
                CellToJsonValue = JsonString(CStr(cell.Value))
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