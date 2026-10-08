- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Public iTipologia As Integer
Public Sub CalculoExcel()
    Dim NombreHoja As String

    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IM_MOMENT_EXCEL"
            iTipologia = 0
            
        Case "IM_FLUSHEP_EXCEL"
            iTipologia = 1
            
        Case "IM_BRACING_EXCEL"
            iTipologia = 2
            
        Case "IM_BRACINGEP_EXCEL"
            iTipologia = 3
            
        Case "IM_SHEAREP_EXCEL"
            iTipologia = 4
            
        Case "IM_SPLICEEP_EXCEL"
            iTipologia = 5
            
        Case "IM_SPLICECP_EXCEL"
            iTipologia = 6
            
    End Select

    Call InterfazHojaConexion
End Sub

Public Sub InterfazHojaConexion()

'Application.Visible = False

Dim fso As Object
Set fso = VBA.CreateObject("Scripting.FileSystemObject")

Dim GenerarCopia As Boolean
Dim RutaHojaConexion As String
Dim RutaCarpetaReportes As String
Dim NombreCarpetaReportes As String
Dim RutaArchivoOrigen As String
Dim RutaArchivoCopia As String
Dim NombreArchivoCopia As String

Dim Con0 As Integer
Dim Numero0 As Double
Dim Doble0 As Double
Dim LibroConexion As Workbook
Dim LibroConexion6bolts As Workbook
Dim HojaSabana As Worksheet
Dim HojaConexion As Worksheet
Dim HojaConexion6bolts As Worksheet
Dim NombreCampoFilasTension As String
Dim NombreCampoColumnas As String
Dim NumeFilasTension As Integer
Dim NumeColumnas As Integer
Dim ColuCopiaRatios As Integer
Dim FilaCopiaRatios As Integer
Dim RestaPorcentaje As Integer
Dim MaximoValor As Integer
RestaPorcentaje = 0
MaximoValor = 0

Dim HayFilasTension As Boolean
Dim HayPerfilesLsTs As Boolean

GenerarCopia = False
NombreCarpetaReportes = "REPORTES"

' HayFilasTension Tiene que ser TRUE para uniones a momento extendidas y FALSE en el resto de casos
' HayPerfilesLsTs Tiene que ser TRUE para bracings con gusset plate y FALSE en el resto de casos

HayFilasTension = False
HayPerfilesLsTs = False

Dim NumeTipos As Integer

NumeFilasTension = 2
NumeColumnas = 1
NumeTipos = 7

Dim MaNombreHojaSabana() As String
Dim MaColuCopiaRatios() As String

Dim MaCeldaCopiaRatios() As String

Dim MaNombreHojaJorge() As String
Dim MaNombreHojaJorge2() As String

ReDim MaNombreHojaSabana(0 To NumeTipos - 1)
ReDim MaColuCopiaRatios(0 To NumeTipos - 1)

ReDim MaCeldaCopiaRatios(0 To NumeTipos - 1)

ReDim MaNombreHojaJorge(0 To NumeTipos - 1)
ReDim MaNombreHojaJorge2(0 To NumeTipos - 1)

'Moment connection

MaNombreHojaSabana(0) = "IM_MOMENT_EXCEL"
MaCeldaCopiaRatios(0) = "Z15"
'MaNombreHojaJorge(0) = "Moment_Tension4bolts_v2.xlsm"
'MaNombreHojaJorge2(0) = "Moment_Tension6bolts_v7.xlsm"
MaNombreHojaJorge(0) = "seedfile_M_T6&T4bolts_v12.xlsm"
MaNombreHojaJorge2(0) = ""


'Flush end moment connection

MaNombreHojaSabana(1) = "IM_FLUSHEP_EXCEL"
MaCeldaCopiaRatios(1) = "Y15"
'MaNombreHojaJorge(1) = "Moment_Flush_End_v1.xlsm"
MaNombreHojaJorge(1) = "seedfile_M_FlushE_v5.2.xlsm"
MaNombreHojaJorge2(1) = ""

'Bracing with gusset plate

MaNombreHojaSabana(2) = "IM_BRACING_EXCEL"
MaCeldaCopiaRatios(2) = "P15"
'MaNombreHojaJorge(2) = "BracingLs_v1.xlsm"
'MaNombreHojaJorge2(2) = "BracingTs_v1.xlsm"
MaNombreHojaJorge(2) = "seedfile BracingLs_v1.1.xlsm"
MaNombreHojaJorge2(2) = "seedfile BracingTs_v1.1.xlsm"


'Bracing with end plate

MaNombreHojaSabana(3) = "O_CAL_AP02_changes"
MaColuCopiaRatios(3) = Range("CN:CN").column
'MaNombreHojaJorge(3) = "BracingEndPl_v1.xlsm"
MaNombreHojaJorge(3) = "seedfile BracingEndPl_v2.1.xlsm"
MaNombreHojaJorge2(3) = ""

'Shear end plate connection

'MaNombreHojaSabana(4) = "O_CAL_CP05_new"
MaNombreHojaSabana(4) = "IM_SHEAREP_EXCEL"
MaCeldaCopiaRatios(4) = "Y15"
'MaNombreHojaJorge(4) = "Shear End-Plate_v1.xlsm"
MaNombreHojaJorge(4) = "seedfile_Shear End-Plate_v3.1.xlsm"
MaNombreHojaJorge2(4) = ""

'Splice with end plate

MaNombreHojaSabana(5) = "IM_SPLICEEP_EXCEL"
MaCeldaCopiaRatios(5) = "U15"
'MaNombreHojaJorge(5) = "Splice End Plate_6bolts_v1.xlsm"
MaNombreHojaJorge(5) = "seedfile_Splice End Plate_T6bolts_v8.1.xlsm"
MaNombreHojaJorge2(5) = ""

'Splice with cover plate

MaNombreHojaSabana(6) = "O_CAL_SPLICECOVER"
MaColuCopiaRatios(6) = Range("CC:CC").column
'MaNombreHojaJorge(6) = "Splice Cover Plates_v2.xlsm"
MaNombreHojaJorge(6) = "seedfile Splice Cover Plates_v2.1.xlsm"
MaNombreHojaJorge2(6) = ""

Dim NumeRangos As Integer
Dim MaNombreArchivosImpresion() As String
Dim MaRutasImpresion() As String
Dim MaNombreHojasImpresion() As String
Dim MaHojasImpresion() As Worksheet
Dim MaRangosImpresion() As String
Dim MaMaRangosImpresion() As Variant

ReDim MaNombreHojasImpresion(0 To NumeTipos - 1)
ReDim MaHojasImpresion(0 To NumeTipos - 1)
ReDim MaRutasImpresion(0 To NumeTipos - 1)
ReDim MaHojasImpresion(0 To NumeTipos - 1)
ReDim MaMaRangosImpresion(0 To NumeTipos - 1)

' MOMENTO

NumeRangos = 1
ReDim MaRangosImpresion(0 To NumeRangos - 1)
'MaRutasImpresion(0) = "C:\Users\r.cabello.a\OneDrive - Tecnicas Reunidas, S.A\DATOS\STADE\CONNECTION DESIGN\REPORTES_JPG\MOMENT"
MaRutasImpresion(0) = "C:\Users\lgmontero\OneDrive - Tecnicas Reunidas, S.A\STADE\CONNECTION DESIGN\MEMORIA\REPORTES_JPG\MOMENT"
MaNombreHojasImpresion(0) = "MC_Output Reduced"
MaRangosImpresion(0) = "A1:R121"

MaMaRangosImpresion(0) = MaRangosImpresion

' MOMENTO FLUSH END

NumeRangos = 1
ReDim MaRangosImpresion(0 To NumeRangos - 1)
MaRutasImpresion(1) = "C:\Users\lgmontero\OneDrive - Tecnicas Reunidas, S.A\STADE\CONNECTION DESIGN\MEMORIA\REPORTES_JPG\MOMENT"
MaNombreHojasImpresion(1) = "MF_Output Reduced"
MaRangosImpresion(0) = "A1:R117"

MaMaRangosImpresion(1) = MaRangosImpresion

'BRACINGS GUSSET PLATE

NumeRangos = 4
ReDim MaRangosImpresion(0 To NumeRangos - 1)
MaRutasImpresion(2) = "C:\Users\lgmontero\OneDrive - Tecnicas Reunidas, S.A\STADE\CONNECTION DESIGN\MEMORIA\REPORTES_JPG\BRACING LSTS"
MaNombreHojasImpresion(2) = "Br Conn Section N_t-c"
MaRangosImpresion(0) = "A2:M74"
MaRangosImpresion(1) = "A75:M96"
MaRangosImpresion(2) = "A2:M80"
MaRangosImpresion(3) = "A81:M95"

MaMaRangosImpresion(2) = MaRangosImpresion

'BRACINGS EP

NumeRangos = 2
ReDim MaRangosImpresion(0 To NumeRangos - 1)
MaRutasImpresion(3) = "C:\Users\lgmontero\OneDrive - Tecnicas Reunidas, S.A\STADE\CONNECTION DESIGN\MEMORIA\REPORTES_JPG\BRACING EP"
MaNombreHojasImpresion(3) = "S-EP Connections"
MaRangosImpresion(0) = "A2:M66"

MaMaRangosImpresion(3) = MaRangosImpresion

' CORTANTE

NumeRangos = 2
ReDim MaRangosImpresion(0 To NumeRangos - 1)
'MaRutasImpresion(4) = "C:\Users\r.cabello.a\OneDrive - Tecnicas Reunidas, S.A\DATOS\STADE\CONNECTION DESIGN\REPORTES_JPG\CORTANTE"
MaRutasImpresion(4) = "C:\Users\lgmontero\OneDrive - Tecnicas Reunidas, S.A\STADE\CONNECTION DESIGN\MEMORIA\REPORTES_JPG\CORTANTE"
MaNombreHojasImpresion(4) = "S-EP Connections"
MaRangosImpresion(0) = "A2:M70"
MaRangosImpresion(1) = "A71:M91"


MaMaRangosImpresion(4) = MaRangosImpresion




ColuCopiaRatios = Range(MaCeldaCopiaRatios(iTipologia)).column
FilaCopiaRatios = Range(MaCeldaCopiaRatios(iTipologia)).Row


NombreCampoFilasTension = "nbrtension_ep_AME"
NombreCampoColumnas = "nbc_gp"

Set LibroConexion = Application.Workbooks(MaNombreHojaJorge(iTipologia))
Set HojaConexion = LibroConexion.Worksheets("Data")

'Set MaHojasImpresion(iTipologia) = LibroConexion.Worksheets(MaNombreHojasImpresion(iTipologia))

If HayFilasTension Then

    Set LibroConexion6bolts = Application.Workbooks(MaNombreHojaJorge2(iTipologia))
    Set HojaConexion6bolts = LibroConexion6bolts.Worksheets("Data")
    
    Set MaHojasImpresion(iTipologia) = LibroConexion6bolts.Worksheets(MaNombreHojasImpresion(iTipologia))
    
ElseIf HayPerfilesLsTs Then

    Set LibroConexion6bolts = Application.Workbooks(MaNombreHojaJorge2(iTipologia))
    Set HojaConexion6bolts = LibroConexion6bolts.Worksheets("Data")
    
    Set MaHojasImpresion(iTipologia) = LibroConexion6bolts.Worksheets(MaNombreHojasImpresion(iTipologia))
     
End If

Dim RS0 As ADODB.Recordset
Dim RSOutputData As ADODB.Recordset
Dim RutaArchivoBD As String
Dim RutaArchivoBDLibroConexion As String
Dim RutaArchivoBDLibroConexion6bolts As String
Dim NombreHoja As String
Dim NombreHojaLibroConexion As String
Dim NombreHojaLibroConexion6bolts As String
Dim Rango As String
Dim RangoLibroConexion As String
Dim RangoLibroConexion6bolts As String

'RutaArchivoBD = Application.WorksheetFunction.Substitute(ThisWorkbook.Path, "/", "\") & "\" & ThisWorkbook.Name
RutaArchivoBD = "C:\Users\mperozo\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\CARGADOR BD CONEXIONES HASSI.xlsm"
NombreHoja = MaNombreHojaSabana(iTipologia)
Rango = "B14:CP2000"
Set HojaSabana = ThisWorkbook.Worksheets(NombreHoja)

'RutaArchivoBDLibroConexion = LibroConexion.Path & "\" & LibroConexion.Name
RutaArchivoBDLibroConexion = "C:\Users\mperozo\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\Formuladas en Excel (Jorge Burbano)" & "\" & LibroConexion.Name

NombreHojaLibroConexion = "OutputData"
RangoLibroConexion = "A1:CP2"

If HayFilasTension Then

    'RutaArchivoBDLibroConexion6bolts = LibroConexion6bolts.Path & "\" & LibroConexion6bolts.Name
    RutaArchivoBDLibroConexion6bolts = "C:\Users\lgmontero\OneDrive - Tecnicas Reunidas, S.A\STADE\CONNECTION DESIGN\Formuladas en Excel (Jorge Burbano)\Moment" & "\" & LibroConexion6bolts.Name
    NombreHojaLibroConexion6bolts = "OutputData"
    RangoLibroConexion6bolts = "A1:CP2"

ElseIf HayPerfilesLsTs Then
    
    'RutaArchivoBDLibroConexion6bolts = LibroConexion6bolts.Path & "\" & LibroConexion6bolts.Name
    'RutaArchivoBDLibroConexion6bolts = "C:\Users\lgmontero\OneDrive - Tecnicas Reunidas, S.A\STADE\CONNECTION DESIGN\Formuladas en Excel (Jorge Burbano)\Bracings" & "\" & LibroConexion6bolts.Name
    RutaArchivoBDLibroConexion6bolts = "C:\Users\r.cabello.a\OneDrive - Tecnicas Reunidas, S.A\DATOS\HASSI\Formuladas en Excel (Jorge Burbano)" & "\" & LibroConexion6bolts.Name
    NombreHojaLibroConexion6bolts = "OutputData"
    RangoLibroConexion6bolts = "A1:CP2"


End If

Call GetValuesFromExcelFile(RutaArchivoBD, NombreHoja, Rango, RS0)

RS0.Open

Dim ConHojasImpresion As Integer
Dim Colu As Integer
Dim NombreCampo As String
Dim NombreCampo6bolts As String

Con0 = 0
ConHojasImpresion = 1
While Not RS0.EOF

    Colu = 1
    NombreCampo = HojaConexion.Cells(1, Colu).value
    If HayFilasTension Or HayPerfilesLsTs Then
    
        NombreCampo6bolts = HojaConexion6bolts.Cells(1, Colu).value
        
        
    End If
    
    If HayFilasTension Then NumeFilasTension = CInt(RS0.Fields(NombreCampoFilasTension).value)
    If HayPerfilesLsTs Then NumeColumnas = CInt(RS0.Fields(NombreCampoColumnas).value)
    
    If NumeFilasTension = 2 And NumeColumnas = 1 Then
    
        While NombreCampo <> "" And NombreCampo <> "Goal"

            If NombreCampo = "MzEd_Porcen" Then
                HojaConexion.Cells(2, Colu).value = RS0.Fields(NombreCampo).value - RestaPorcentaje
                'Escribe el momento resultante
                Range("BE" & FilaCopiaRatios).value = HojaConexion.Cells(2, Colu).value
            Else
                HojaConexion.Cells(2, Colu).value = RS0.Fields(NombreCampo).value
                
            End If
            
            Colu = Colu + 1
            NombreCampo = HojaConexion.Cells(1, Colu).value
        
        Wend
        
        LibroConexion.Save
        
        Call GetValuesFromExcelFile(RutaArchivoBDLibroConexion, NombreHojaLibroConexion, RangoLibroConexion, RSOutputData)
    
        RSOutputData.Open
        HojaSabana.Cells(FilaCopiaRatios, ColuCopiaRatios).CopyFromRecordset RSOutputData
        
        If GenerarCopia Then
        
            NombreArchivoCopia = LibroConexion.Name
            RutaHojaConexion = LibroConexion.Path
            RutaArchivoOrigen = RutaArchivoBDLibroConexion
            
        End If
      
    ElseIf NumeFilasTension = 3 Then
    
        While NombreCampo6bolts <> ""
        
            If NombreCampo = "MzEd_Porcen" Then
                
                HojaConexion6bolts.Cells(2, Colu).value = RS0.Fields(NombreCampo6bolts).value - RestaPorcentaje
                'Escribe el momento resultante
                Range("BE" & FilaCopiaRatios).value = RS0.Fields(NombreCampo).value - RestaPorcentaje
            Else
                HojaConexion6bolts.Cells(2, Colu).value = RS0.Fields(NombreCampo6bolts).value
                
            End If
            
            Colu = Colu + 1
            NombreCampo6bolts = HojaConexion6bolts.Cells(1, Colu).value
        
        Wend
        
        LibroConexion6bolts.Save
        
        Call GetValuesFromExcelFile(RutaArchivoBDLibroConexion6bolts, NombreHojaLibroConexion6bolts, RangoLibroConexion6bolts, RSOutputData)
    
        RSOutputData.Open
        HojaSabana.Cells(FilaCopiaRatios, ColuCopiaRatios).CopyFromRecordset RSOutputData
        
        If GenerarCopia Then
        
            NombreArchivoCopia = LibroConexion6bolts.Name
            RutaHojaConexion = LibroConexion6bolts.Path
            RutaArchivoOrigen = RutaArchivoBDLibroConexion6bolts
        
        End If
        
    ElseIf NumeColumnas = 2 Then
    
        While NombreCampo6bolts <> ""
        
            If NombreCampo = "MzEd_Porcen" Then
                HojaConexion6bolts.Cells(2, Colu).value = RS0.Fields(NombreCampo6bolts).value - RestaPorcentaje
                Range("BE" & FilaCopiaRatios).value = RS0.Fields(NombreCampo).value - RestaPorcentaje
            Else
                HojaConexion6bolts.Cells(2, Colu).value = RS0.Fields(NombreCampo6bolts).value
               
            End If
            
            Colu = Colu + 1
            NombreCampo6bolts = HojaConexion6bolts.Cells(1, Colu).value
        
        Wend
        
        LibroConexion6bolts.Save
        
        Call GetValuesFromExcelFile(RutaArchivoBDLibroConexion6bolts, NombreHojaLibroConexion6bolts, RangoLibroConexion6bolts, RSOutputData)
    
        RSOutputData.Open
        HojaSabana.Cells(FilaCopiaRatios, ColuCopiaRatios).CopyFromRecordset RSOutputData
        
        If GenerarCopia Then
        
            'NombreArchivoCopia = LibroConexion6bolts.Name
            'RutaHojaConexion = LibroConexion6bolts.Path
            'RutaArchivoOrigen = RutaArchivoBDLibroConexion6bolts
        
        End If
           
    
    End If
    
    If GenerarCopia Then
    
        RutaCarpetaReportes = RutaHojaConexion & "\" & NombreCarpetaReportes
        
        If Not fso.FolderExists(RutaCarpetaReportes) Then
        
            fso.CreateFolder (RutaCarpetaReportes)
        
        End If
        
        NombreArchivoCopia = Application.WorksheetFunction.Substitute(NombreArchivoCopia, ".xlsm", "") & "_" & RS0.Fields("Elemento_Secundario_VIGA").value _
                             & "_" & RS0.Fields("Elemento_Principal_COLUMNA").value & ".xlsm"
        RutaArchivoCopia = RutaCarpetaReportes & "\" & NombreArchivoCopia
        
        fso.CopyFile RutaArchivoOrigen, RutaArchivoCopia, True
    
    End If
    
    'NumeRangos = UBound(MaMaRangosImpresion(iTipologia)) + 1
    ReDim MaNombreArchivosImpresion(0 To NumeRangos - 1)
    
    ''For i = 0 To NumeRangos - 1
    
        'MaNombreArchivosImpresion(i) = ConHojasImpresion & "_" & MaNombreHojaJorge(iTipologia) & "_" & RS0.Fields("BEAM").Value
        
        'If HayFilasTension Then
        
            'MaNombreArchivosImpresion(i) = MaNombreArchivosImpresion(i) & "_" & RS0.Fields("COLUMN").Value
        
        'End If
                                           
        'ConHojasImpresion = ConHojasImpresion + 1
    
    'Next
    
    'MaRangosImpresion = MaMaRangosImpresion(iTipologia)
    'ExportToJPG MaHojasImpresion(iTipologia), MaRangosImpresion, MaRutasImpresion(iTipologia), MaNombreArchivosImpresion
      
    
   
   
   'Analizamos ese valor
   If Range("BD" & FilaCopiaRatios).value > 1 Then
    RestaPorcentaje = RestaPorcentaje + 1
   Else
    RS0.MoveNext
    FilaCopiaRatios = FilaCopiaRatios + 1
    Con0 = Con0 + 1
    RestaPorcentaje = 0
   End If
   
      
    

Wend

End Sub


Public Sub GetValuesFromExcelFile(RutaArchivoBD As String, NombreHoja As String, Rango As String, RecordSet0 As ADODB.Recordset)
 
Dim ConnectionString As String
Dim QueryString As String

Dim cnn As ADODB.Connection
 
Set RecordSet0 = New ADODB.Recordset

ConnectionString = "Provider=Microsoft.ace.OLEDB.12.0; Data Source=""" & RutaArchivoBD & """;" & _
                   "Extended Properties=""Excel 12.0;HDR=Yes;ReadOnly=True"";"
 
QueryString = "SELECT * FROM [" & NombreHoja & "$" & Rango & "]"

RecordSet0.Open QueryString, ConnectionString, ADODB.CursorTypeEnum.adOpenStatic, ADODB.LockTypeEnum.adLockReadOnly
 
RecordSet0.Close
 
'Dim Connection0 As New ADODB.Connection
 
'Connection0.ConnectionString = ConnectionString
'Connection0.Open
'RecordSet0.ActiveConnection = Connection
 
End Sub


Public Sub CompletarValores()
 
Dim LibroOrigen As Workbook
 
Dim HojaOrigen As Worksheet
Dim HojaReferencia As Worksheet
 
Set LibroOrigen = ThisWorkbook
 
Set HojaOrigen = LibroOrigen.Worksheets("O_CAL_MP01_new")
Set HojaReferencia = LibroOrigen.Worksheets("O_CAL_MP01_01")
 
Dim MaColuCopia(0 To 1)
 
MaColuCopia(0) = Range("AJ:AJ").column
MaColuCopia(1) = Range("AL:AL").column
'MaColuCopia(2) = Range("Z:Z").Column
'MaColuCopia(3) = Range("AA:AA").Column
'MaColuCopia(4) = Range("AB:AB").Column
'MaColuCopia(5) = Range("AC:AC").Column
'MaColuCopia(6) = Range("AD:AD").Column
'MaColuCopia(7) = Range("AE:AE").Column
'MaColuCopia(8) = Range("AF:AF").Column
'MaColuCopia(9) = Range("AG:AG").Column
'MaColuCopia(10) = Range("AH:AH").Column
'MaColuCopia(11) = Range("AI:AI").Column
'MaColuCopia(12) = Range("AJ:AJ").Column
'MaColuCopia(13) = Range("AS:AS").Column
'MaColuCopia(14) = Range("BD:BD").Column
 
Dim Con0 As Integer
Dim CodigoOrigen As String
Dim CodigoReferencia As String
Con0 = 0
For i = 2 To 68
 
    CodigoReferencia = HojaReferencia.Cells(i, 1).value
    For j = 2 To 702
        CodigoOrigen = HojaOrigen.Cells(j, 1).value
        If CodigoOrigen = CodigoReferencia Then
            For k = 0 To 1
                
                HojaReferencia.Cells(i, MaColuCopia(k)).Copy
                HojaOrigen.Cells(j, MaColuCopia(k)).PasteSpecial xlPasteValues
                HojaOrigen.Cells(j, MaColuCopia(k)).Interior.ColorIndex = 15
            
            Next
            j = 702
            Con0 = Con0 + 1
        End If
    Next
 
Next
 
End Sub

Public Sub ExportToJPG(HojaExcel As Worksheet, MaRangosAddress() As String, RutaCarpeta As String, MaNombreArchivosImagen() As String)

 Dim RangoImpresion As Range
 Dim oChrtO As ChartObject
 Dim lWidth As Long, lHeight As Long

For i = 0 To UBound(MaRangosAddress, 1)

    Set RangoImpresion = HojaExcel.Range(MaRangosAddress(i))
    
     RangoImpresion.CopyPicture xlScreen, xlPicture
     lWidth = RangoImpresion.Width
     lHeight = RangoImpresion.Height
    
     Set oChrtO = HojaExcel.ChartObjects.Add(Left:=0, Top:=0, Width:=lWidth, Height:=lHeight)
    
     oChrtO.Activate
     With oChrtO.Chart
     
        .Paste
        .Export Filename:=RutaCarpeta & "\" & MaNombreArchivosImagen(i) & ".jpg", Filtername:="JPG"
      
     End With

 oChrtO.Delete


Next




End Sub

-------------------------------------------------------------------------------
VBA MACRO Hoja42.cls 