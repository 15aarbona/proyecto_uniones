Attribute VB_Name = "AI_Client"
Option Explicit

' ============================================================================
' Cliente de Excel <-> servidor de inferencia (fase de pruebas, columnas de prueba).
'
' QUÉ HACE ESTE MÓDULO
'   - Sub SendToAI()          [botón "Enviar a IA"]        envía TODAS las filas de la
'                              hoja activa a POST /predict y escribe la respuesta.
'   - Sub ValidateAndSend()   [botón "Validar y enviar"]   envía las filas ya predichas
'                              (con los valores que el ingeniero haya editado a mano) a
'                              POST /validate, para que el servidor las guarde de cara a
'                              un reentreno futuro.
'
' DISEÑO: NO asume nombres de columna fijos. Lee la fila de cabeceras (fila 1) tal cual
' esté en la hoja, manda esas columnas tal cual al servidor, y escribe cualquier columna
' nueva que venga en la respuesta (p.ej. "pred_valor_A") añadiéndola al final si no existe
' ya. Así, cuando las columnas de entrada/salida reales estén cerradas, no hace falta tocar
' esta macro: basta con que la hoja tenga esas cabeceras.
'
' CÓMO INSTALAR
'   1. Abre el editor VBA (Alt+F11) en el libro donde quieras usar esto.
'   2. Archivo -> Importar archivo... -> selecciona este AI_Client.bas
'   3. Herramientas -> Referencias -> marca "Microsoft WinHTTP Services, version 5.1"
'      (si no aparece marcada, dará error "ActiveX no puede crear el objeto").
'   4. Ajusta las constantes SERVER_URL / API_KEY / SHEET_NAME más abajo.
'   5. Inserta dos botones (Desarrollador -> Insertar -> Botón de formulario) y asígnales
'      las macros AI_Client.SendToAI y AI_Client.ValidateAndSend.
' ============================================================================

' --- Configuración: EDITAR AQUÍ --------------------------------------------------------
Private Const SERVER_URL As String = "http://127.0.0.1:8080"   ' cambiar al equipo central cuando toque
Private Const API_KEY As String = "changeme"                     ' debe coincidir con AI_API_KEY del servidor
Private Const SHEET_NAME As String = "Datos_IA"                 ' hoja donde está la tabla de entrada
Private Const HEADER_ROW As Long = 1                             ' fila de cabeceras
Private Const FIRST_DATA_ROW As Long = 2                         ' primera fila de datos
Private Const STATUS_COLUMN_NAME As String = "Estado_IA"        ' columna de estado (se crea sola si no existe)
Private Const TIMEOUT_MS As Long = 30000                         ' 30 s
' ----------------------------------------------------------------------------------------

Private Const STATUS_PREDICHO As String = "Predicho"
Private Const STATUS_VALIDADO As String = "Validado y enviado"


' ============================================================================
' BOTÓN 1: "Enviar a IA" — manda TODAS las filas con datos a /predict.
' ============================================================================
Public Sub SendToAI()
    Dim ws As Worksheet
    Dim lastRow As Long, lastCol As Long
    Dim headers() As String
    Dim payload As String
    Dim response As String
    Dim httpStatus As Long

    On Error GoTo ErrHandler

    Set ws = GetSheet(SHEET_NAME)
    lastCol = GetLastColumn(ws)
    lastRow = GetLastRow(ws)

    If lastRow < FIRST_DATA_ROW Then
        MsgBox "No hay filas de datos en la hoja '" & SHEET_NAME & "'.", vbExclamation
        Exit Sub
    End If

    headers = ReadHeaders(ws, lastCol)
    payload = BuildRowsJson(ws, headers, FIRST_DATA_ROW, lastRow)

    Application.StatusBar = "Enviando " & (lastRow - FIRST_DATA_ROW + 1) & " fila(s) a la IA..."
    If Not HttpPostJson(SERVER_URL & "/predict", payload, response, httpStatus) Then
        MsgBox "No se ha podido contactar con el servidor de IA:" & vbCrLf & response, vbCritical
        GoTo CleanExit
    End If

    If httpStatus <> 200 Then
        MsgBox "El servidor devolvió un error (HTTP " & httpStatus & "):" & vbCrLf & response, vbCritical
        GoTo CleanExit
    End If

    WriteResponseToSheet ws, headers, FIRST_DATA_ROW, lastRow, response, STATUS_PREDICHO
    MsgBox "Predicción recibida para " & (lastRow - FIRST_DATA_ROW + 1) & " fila(s).", vbInformation

CleanExit:
    Application.StatusBar = False
    Exit Sub

ErrHandler:
    Application.StatusBar = False
    MsgBox "Error inesperado en SendToAI: " & Err.Description, vbCritical
End Sub


' ============================================================================
' BOTÓN 2: "Validar y enviar" — manda las filas marcadas como "Predicho" (con los valores
' que el ingeniero haya editado a mano) a /validate, para que el servidor las guarde.
' ============================================================================
Public Sub ValidateAndSend()
    Dim ws As Worksheet
    Dim lastRow As Long, lastCol As Long
    Dim headers() As String
    Dim statusCol As Long
    Dim payload As String
    Dim response As String
    Dim httpStatus As Long
    Dim r As Long, n As Long

    On Error GoTo ErrHandler

    Set ws = GetSheet(SHEET_NAME)
    lastCol = GetLastColumn(ws)
    lastRow = GetLastRow(ws)
    headers = ReadHeaders(ws, lastCol)
    statusCol = FindColumn(headers, STATUS_COLUMN_NAME)

    If statusCol = 0 Then
        MsgBox "No encuentro la columna '" & STATUS_COLUMN_NAME & "'. Pulsa antes 'Enviar a IA'.", vbExclamation
        Exit Sub
    End If

    ' Solo se validan/envían las filas que ya tienen una predicción pendiente de validar.
    n = 0
    payload = "{""rows"": ["
    For r = FIRST_DATA_ROW To lastRow
        If CStr(ws.Cells(r, statusCol).value) = STATUS_PREDICHO Then
            If n > 0 Then payload = payload & ","
            payload = payload & RowToJson(ws, headers, r)
            n = n + 1
        End If
    Next r
    payload = payload & "]}"

    If n = 0 Then
        MsgBox "No hay filas en estado '" & STATUS_PREDICHO & "' para validar." & vbCrLf & _
               "Pulsa primero 'Enviar a IA', revisa/edita los valores y vuelve a intentarlo.", vbExclamation
        Exit Sub
    End If

    Application.StatusBar = "Enviando " & n & " fila(s) validada(s)..."
    If Not HttpPostJson(SERVER_URL & "/validate", payload, response, httpStatus) Then
        MsgBox "No se ha podido contactar con el servidor de IA:" & vbCrLf & response, vbCritical
        GoTo CleanExit
    End If

    If httpStatus <> 200 Then
        MsgBox "El servidor devolvió un error (HTTP " & httpStatus & "):" & vbCrLf & response, vbCritical
        GoTo CleanExit
    End If

    ' Marcar como validadas las filas que se han enviado
    For r = FIRST_DATA_ROW To lastRow
        If CStr(ws.Cells(r, statusCol).value) = STATUS_PREDICHO Then
            ws.Cells(r, statusCol).value = STATUS_VALIDADO & " (" & Format(Now, "yyyy-mm-dd hh:nn") & ")"
        End If
    Next r

    MsgBox n & " fila(s) validada(s) y guardada(s) en el servidor.", vbInformation

CleanExit:
    Application.StatusBar = False
    Exit Sub

ErrHandler:
    Application.StatusBar = False
    MsgBox "Error inesperado en ValidateAndSend: " & Err.Description, vbCritical
End Sub


' ============================================================================
' HTTP (WinHTTP nativo, sin dependencias externas)
' ============================================================================
Private Function HttpPostJson(url As String, jsonBody As String, ByRef outResponse As String, ByRef outStatus As Long) As Boolean
    Dim http As Object
    On Error GoTo Fail

    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.Open "POST", url, False
    http.SetRequestHeader "Content-Type", "application/json; charset=utf-8"
    http.SetRequestHeader "X-API-Key", API_KEY
    http.SetTimeouts TIMEOUT_MS, TIMEOUT_MS, TIMEOUT_MS, TIMEOUT_MS
    http.Send Utf8Encode(jsonBody)

    outStatus = http.Status
    outResponse = Utf8Decode(http.responseBody)
    HttpPostJson = True
    Exit Function

Fail:
    outResponse = "No se pudo conectar con " & url & " -> " & Err.Description & _
                  vbCrLf & "Comprueba que el servidor está arrancado y la URL/puerto son correctos."
    outStatus = 0
    HttpPostJson = False
End Function


' ============================================================================
' Lectura/escritura de la hoja
' ============================================================================
Private Function GetSheet(sheetName As String) As Worksheet
    On Error Resume Next
    Set GetSheet = ThisWorkbook.Worksheets(sheetName)
    On Error GoTo 0
    If GetSheet Is Nothing Then
        MsgBox "No existe la hoja '" & sheetName & "'. Revisa la constante SHEET_NAME.", vbCritical
        End
    End If
End Function

Private Function GetLastRow(ws As Worksheet) As Long
    GetLastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).row
    If GetLastRow < HEADER_ROW Then GetLastRow = HEADER_ROW
End Function

Private Function GetLastColumn(ws As Worksheet) As Long
    GetLastColumn = ws.Cells(HEADER_ROW, ws.Columns.Count).End(xlToLeft).Column
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

Private Function FindColumn(headers() As String, name As String) As Long
    Dim i As Long
    For i = LBound(headers) To UBound(headers)
        If headers(i) = name Then
            FindColumn = i
            Exit Function
        End If
    Next i
    FindColumn = 0
End Function

' Construye {"rows": [ {...}, {...} ]} para el rango [firstRow, lastRow]
Private Function BuildRowsJson(ws As Worksheet, headers() As String, firstRow As Long, lastRow As Long) As String
    Dim r As Long
    Dim sb As String
    sb = "{""rows"": ["
    For r = firstRow To lastRow
        If r > firstRow Then sb = sb & ","
        sb = sb & RowToJson(ws, headers, r)
    Next r
    sb = sb & "]}"
    BuildRowsJson = sb
End Function

' Una fila -> objeto JSON plano {"Cabecera1": valor, "Cabecera2": valor, ...}
' Los valores numéricos se mandan como número, el resto como texto. Celdas vacías -> null.
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
    If IsEmpty(cell.value) Or cell.value = "" Then
        CellToJsonValue = "null"
    ElseIf IsNumeric(cell.value) Then
        CellToJsonValue = Replace(CStr(cell.value), ",", ".")   ' por si el sistema usa coma decimal
    Else
        CellToJsonValue = JsonString(CStr(cell.value))
    End If
End Function

' Escribe la respuesta de /predict (lista de objetos) de vuelta en la hoja. Las columnas de
' la respuesta que no existan ya en la hoja se añaden al final (una sola vez).
Private Sub WriteResponseToSheet(ws As Worksheet, ByRef headers() As String, firstRow As Long, lastRow As Long, _
                                 jsonResponse As String, newStatus As String)
    Dim rowsArr As Collection
    Dim r As Long, i As Long
    Dim rowObj As Object
    Dim key As Variant
    Dim col As Long
    Dim lastCol As Long
    Dim statusCol As Long

    Set rowsArr = JsonParseRowsField(jsonResponse, "rows")
    lastCol = UBound(headers)

    ' Asegurar columna de estado
    statusCol = FindColumn(headers, STATUS_COLUMN_NAME)
    If statusCol = 0 Then
        lastCol = lastCol + 1
        ws.Cells(HEADER_ROW, lastCol).value = STATUS_COLUMN_NAME
        ReDim Preserve headers(1 To lastCol)
        headers(lastCol) = STATUS_COLUMN_NAME
        statusCol = lastCol
    End If

    i = 1
    For r = firstRow To lastRow
        If i > rowsArr.Count Then Exit For
        Set rowObj = rowsArr(i)
        For Each key In rowObj.Keys
            col = FindColumn(headers, CStr(key))
            If col = 0 Then
                lastCol = lastCol + 1
                ws.Cells(HEADER_ROW, lastCol).value = CStr(key)
                ReDim Preserve headers(1 To lastCol)
                headers(lastCol) = CStr(key)
                col = lastCol
                If key = STATUS_COLUMN_NAME Then statusCol = lastCol
            End If
            ws.Cells(r, col).value = rowObj(key)
        Next key
        ws.Cells(r, statusCol).value = newStatus
        i = i + 1
    Next r
End Sub


' ============================================================================
' JSON — serializador/parser mínimo (suficiente para objetos planos: string/número/bool/
' null, y una lista de objetos planos bajo una clave dada, como "rows"). No pretende ser un
' parser JSON general; si el modelo real necesita estructuras anidadas, sustituir por la
' librería VBA-JSON (Tim Hall, github.com/VBA-tools/VBA-JSON).
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

' Extrae el array de objetos bajo la clave `field` (p.ej. "rows") de un JSON de nivel
' superior tipo {"rows": [ {...}, {...} ], "otro": ...}. Devuelve una Collection de
' Scripting.Dictionary (clave -> valor, valores ya como String/Double/Boolean/Null).
Private Function JsonParseRowsField(json As String, field As String) As Collection
    Dim result As New Collection
    Dim keyPos As Long, arrStart As Long, arrEnd As Long
    Dim depth As Long, i As Long
    Dim objStart As Long
    Dim inString As Boolean, prevChar As String

    keyPos = InStr(json, """" & field & """")
    If keyPos = 0 Then
        Set JsonParseRowsField = result
        Exit Function
    End If
    arrStart = InStr(keyPos, json, "[")

    ' localizar el cierre del array llevando la cuenta de corchetes (respetando strings)
    depth = 0: inString = False: prevChar = ""
    For i = arrStart To Len(json)
        Dim ch As String
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
                If depth = 0 Then arrEnd = i: Exit For
            End If
        End If
        prevChar = ch
    Next i

    i = arrStart + 1
    Do While i < arrEnd
        Dim c2 As String
        c2 = Mid$(json, i, 1)
        If c2 = "{" Then
            objStart = i
            Dim objDepth As Long
            objDepth = 0: inString = False: prevChar = ""
            Dim j As Long
            For j = objStart To arrEnd
                Dim ch2 As String
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
            result.Add JsonParseObject(Mid$(json, objStart, j - objStart + 1))
            i = j + 1
        Else
            i = i + 1
        End If
    Loop

    Set JsonParseRowsField = result
End Function

' Parsea un objeto JSON plano {"clave": valor, ...} -> Scripting.Dictionary
Private Function JsonParseObject(s As String) As Object
    Dim dict As Object
    Set dict = CreateObject("Scripting.Dictionary")
    Dim i As Long, n As Long
    Dim inString As Boolean, prevChar As String
    Dim key As String, val As String
    Dim state As Integer ' 0=esperando clave, 1=en clave, 2=esperando valor, 3=en valor string, 4=en valor literal

    n = Len(s)
    i = 2 ' saltar la '{' inicial
    Do While i < n
        Dim ch As String
        ch = Mid$(s, i, 1)
        Select Case state
            Case 0 ' esperando comillas de clave
                If ch = """" Then
                    state = 1: key = "": i = i + 1
                Else
                    i = i + 1
                End If
            Case 1 ' dentro de la clave
                If ch = """" Then
                    state = 2
                ElseIf ch = "\" Then
                    key = key & Mid$(s, i + 1, 1)
                    i = i + 1
                Else
                    key = key & ch
                End If
                i = i + 1
            Case 2 ' esperando ':' y luego el valor
                If ch = ":" Then
                    ' saltar espacios
                    i = i + 1
                    Do While i <= n And Mid$(s, i, 1) = " "
                        i = i + 1
                    Loop
                    If Mid$(s, i, 1) = """" Then
                        state = 3: val = ""
                        i = i + 1
                    Else
                        state = 4: val = ""
                    End If
                Else
                    i = i + 1
                End If
            Case 3 ' valor string
                If ch = """" Then
                    dict.Add key, UnescapeJson(val)
                    state = 0
                    i = i + 1
                    ' saltar hasta la siguiente comilla de clave o el final
                    Do While i <= n And (Mid$(s, i, 1) = "," Or Mid$(s, i, 1) = " ")
                        i = i + 1
                    Loop
                ElseIf ch = "\" Then
                    val = val & ch & Mid$(s, i + 1, 1)
                    i = i + 2
                Else
                    val = val & ch
                    i = i + 1
                End If
            Case 4 ' valor literal (número, true/false/null) hasta ',' o '}'
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


' ============================================================================
' UTF-8 (WinHTTP.Send necesita bytes; responseBody hay que decodificarlo de vuelta)
' ============================================================================
Private Function Utf8Encode(s As String) As Variant
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 2 ' texto
    stream.Charset = "utf-8"
    stream.Open
    stream.WriteText s
    stream.Position = 0
    stream.Type = 1 ' binario
    Utf8Encode = stream.Read
    stream.Close
End Function

Private Function Utf8Decode(bytes As Variant) As String
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 1 ' binario
    stream.Open
    stream.Write bytes
    stream.Position = 0
    stream.Type = 2 ' texto
    stream.Charset = "utf-8"
    Utf8Decode = stream.ReadText
    stream.Close
End Function