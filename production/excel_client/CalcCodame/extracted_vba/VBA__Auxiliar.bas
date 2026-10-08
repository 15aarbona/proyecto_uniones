- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Public ClaseNombreBD0 As New ClaseNombreBD
Public NombreExcel0 As New NombreExcel

Public RutaLibroExcel As String
Public RutaSabana As String
Public RutaArchivoConfig As String
Public RutaAplicacion As String
Public RutaAplicacionSCS As String
Public RutaAplicacionCodame As String
Public RutaAplicacionExcelEngine As String
Public RutaAplicacionMathcad As String

Public RutaBDPerfiles As String

Public NombresControlesCampos() As String
Public tbl As ListObject
Public iFilaSelecTabla As Integer
Public MaFilasSelecTabla() As Integer

Public RangoHojaActiva As Range
Public AnchoMaximoFormuDatosConex As Integer
Public totalWidth As Integer

Public LongitudMaximaFormuDatos As Integer
Public AlturaMaximoFormuDatosConex As Integer
Public totalHeight As Integer

Public Const EsLectura As Boolean = True

Public Sub ActivarEventos()

RutaAplicacion = "C:\Users\mperozo\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\ChequeoLibreConex\SCS_FORM_VB\bin\Debug\SCS_FORM_VB.exe"

'Argumentos = "Eureka!"

    'X = Shell(RutaAplicacion + " " + Argumentos, vbMinimizedNoFocus)

Application.EnableEvents = True

End Sub

Public Sub MuestraFormuHojas()

BDForm.Show  'vbModeless makes userform 'float'

End Sub

Public Sub Eventos()
    
    Application.EnableEvents = True
    
End Sub

Public UserID As String

Public Sub InstanciaObjetoBD()

Dim Usuario As String

Usuario = Environ("Username")

If IsEmpty(ClaseNombreBD) Then

    Set ClaseNombreBD0 = New ClaseNombreBD
    'Set ClaseNombreBD0.LibroExcel = ThisWorkbook
    
    ' Construir la ruta con la variable UserID
    


        RutaLibroExcel = ThisWorkbook.Name
        'RUTA EN CARPETA COMPARTIDA
        'RutaAplicacion = "\\Fs-ho\132-civil\40-Software\06 - Connections\Production\BDCONEXIONES\BDCONEXIONES.exe"
        RutaAplicacionSCS = "\\fs-ho\132-CIVIL\40-Software\06 - Connections\ACTUALIZACION BD\Production\SCS_CONNEXTOR\SCS_CONNEXTOR.exe"
                
        'RUTA BUENA EN LOCAL
        'RutaAplicacion = "C:\Users\mperozo\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\BDCONEXIONES\BDCONEXIONES\bin\Debug\BDCONEXIONES.exe"
        'RutaAplicacion = "C:\Users\cescobar\OneDrive - Tecnicas Reunidas, S.A\Archivos de Alberto Ruiz-Cabello Lopez - Conexiones\BDCONEXIONES\BDCONEXIONES\bin\Debug\BDCONEXIONES.exe"
        'RutaAplicacionCodame = "C:\Users\mperozo\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\BDCONEXIONES\CalcCodame\bin\Debug\net48\CalcCodame.exe"
        
        RutaAplicacion = "C:\Users\cescobar\OneDrive - Tecnicas Reunidas, S.A\Archivos de Alberto Ruiz-Cabello Lopez - MIGUEL PEROZO\Conexiones\BDCONEXIONES\BDCONEXIONES\bin\Debug\BDCONEXIONES.exe"
        RutaAplicacionCodame = "C:\Users\r.cabello.a\OneDrive - Tecnicas Reunidas, S.A\MACHINE LEARNING CIVIL TR\CalcCodame\CalcCodame.exe"
        RutaAplicacionExcelEngine = "C:\Users\cescobar\OneDrive - Tecnicas Reunidas, S.A\Archivos de Alberto Ruiz-Cabello Lopez - MIGUEL PEROZO\Conexiones\BDCONEXIONES\CalcExcelEngine\bin\Debug\net48\CalcExcelEngine.exe"
        RutaAplicacionMathcad = "C:\Users\cescobar\OneDrive - Tecnicas Reunidas, S.A\Archivos de Alberto Ruiz-Cabello Lopez - MIGUEL PEROZO\Conexiones\BDCONEXIONES\CalcMathcad\bin\Debug\net48\CalcMathcad.exe"
        
        
        'RutaAplicacionMathcad = "C:\Users\r.cabello.a\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\BDCONEXIONES\CalcMathcad\bin\Debug\net48\CalcMathcad.exe"
        'RutaAplicacion = "C:\Users\r.cabello.a\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\BDCONEXIONES\BDCONEXIONES\bin\Debug\BDCONEXIONES.exe"
        'RutaAplicacionCodame = "C:\Users\r.cabello.a\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\BDCONEXIONES\CalcCodame\bin\Debug\net48\CalcCodame.exe"
        
        'RutaAplicacionSCS = "C:\Users\mperozo\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\BDCONEXIONES\SCS_CONNEXTOR\bin\Debug\SCS_CONNEXTOR.exe"
    
    
    'RutaLibroExcel = ThisWorkbook.Name
    'RutaAplicacion = "\\fs-ho\132-CIVIL\40-Software\06 - Connections\BDCONEXIONES.exe"
    
    
End If

End Sub

Public Sub InstanciaObjetoProcesamiento()

Dim Usuario As String

Usuario = Environ("Username")

If IsEmpty(ClaseNombreBD) Then

    Set ClaseNombreBD0 = New ClaseNombreBD
    'Set ClaseNombreBD0.LibroExcel = ThisWorkbook
    
    ' Construir la ruta con la variable UserID
    

    If Usuario = "mperozo" Then
    
        RutaSabana = "C:\Users\mperozo\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\CARGADOR BD CONEXIONES HASSI.xlsm"
        RutaArchivoConfig = "C:\Users\mperozo\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\RIYAS - Configuracion Chequeo Conexiones.xlsx"
        RutaBDPerfiles = "C:\Users\mperozo\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\BDPerfilesMetalicos.db3"
        RutaAplicacion = "C:\Users\mperozo\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\ChequeoLibreConex\ChequeoGeoconex\bin\Debug\ChequeoGeoconex.exe"
    
    ElseIf Usuario = "r.cabello.a" Then
    
        RutaSabana = "C:\Users\r.cabello.a\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\CARGADOR BD CONEXIONES HASSI.xlsm"
        RutaArchivoConfig = "C:\Users\r.cabello.a\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\RIYAS - Configuracion Chequeo Conexiones.xlsx"
        RutaBDPerfiles = "C:\Users\r.cabello.a\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\BDPerfilesMetalicos.db3"
        RutaAplicacion = "C:\Users\r.cabello.a\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\Conexiones\ChequeoLibreConex\ChequeoGeoconex\bin\Debug\ChequeoGeoconex.exe"
        
    ElseIf Usuario = "nevad" Then
    
        RutaLibroExcel = "C:\Users\nevad\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\BASE DE DATOS AMS\CONFIGURADOR AMS_COPIA.xlsm"
        RutaAplicacion = "C:\Users\nevad\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\BDAMS\InterfazFormuExcel\bin\Debug\InterfazFormuExcel.exe"
        
    ElseIf Usuario = "Usuario" Then
    
        RutaLibroExcel = "C:\Users\Usuario\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\BASE DE DATOS AMS\CONFIGURADOR AMS_COPIA.xlsm"
        RutaAplicacion = "C:\Users\Usuario\OneDrive - Tecnicas Reunidas, S.A\MIGUEL PEROZO\BDAMS\InterfazFormuExcel\bin\Debug\InterfazFormuExcel.exe"
    
    End If
    
End If

End Sub

Public Sub CreaNombre()

Dim Rango As Range

Set Rango = ThisWorkbook.Worksheets("TIPOLOGÍAS_CONEXIONES_GRUPOS").Range("H5")

ThisWorkbook.Names.Add "ListaProyectos_TipologiasConexionesGrupos", Rango

End Sub

Public Sub CreaTabla()

Set Rango = ThisWorkbook.Worksheets("CONEXIONES_GENERAL").Range("B44")

'ThisWorkbook.Worksheets("CONEXIONES_GENERAL").ListObjects.Add "Prueba", Rango

ThisWorkbook.Worksheets(1).ListObjects.Add "Prueba", Rango

End Sub

Public Sub KillTheForm()

Unload mensaje

End Sub

Public Function DatosNombreInterfaz(EsLectura As Boolean, Libro As Workbook, Nombre As String, ByRef RangoNombre As Range) As String

    Set NombreExcel0.LibroExcel = Libro
    NombreExcel0.NombreValor = Nombre
    NombreExcel0.DatosNombreExcel
    
    If EsLectura Then
    
        DatosNombreInterfaz = NombreExcel0.HojaAddressNomLectu
        
    Else
    
        DatosNombreInterfaz = NombreExcel0.HojaAddressNomEscri
    
    End If
    
    Set RangoNombre = NombreExcel0.RangoNombre
    
End Function

Public Function DatosTablaInterfaz(EsLectura As Boolean, Libro As Workbook, NombreHoja As String, Tabla As String, ByRef RangoTabla As Range) As String

    Set NombreExcel0.LibroExcel = Libro
    NombreExcel0.TablaValor = Tabla
    NombreExcel0.NombreHojaExcel = NombreHoja
    NombreExcel0.DatosTablaExcel
    
    If EsLectura Then
    
        DatosTablaInterfaz = NombreExcel0.HojaAddressTablaLectu
        
    Else
    
        DatosTablaInterfaz = NombreExcel0.HojaAddressTablaEscri
        
    End If
    
    Set RangoTabla = NombreExcel0.RangoTabla
    
End Function

Public Sub AgregarFiltroInterfaz( _
     texto As String, _
     EsLectura As Boolean, _
     NombreLista As String, _
     RangoBorrado As Range)

    If NombreLista <> "" Then
        texto = texto & DatosNombreInterfaz(EsLectura, ThisWorkbook, NombreLista, RangoBorrado) & " "
    End If

End Sub

Private Function ListaTieneContenido(ByVal Lista As Range) As Boolean

    If Lista Is Nothing Then
        ListaTieneContenido = False
        Exit Function
    End If

    ListaTieneContenido = Application.WorksheetFunction.CountA(Lista) > 0

End Function

Public Function MontarFormulario(ByRef tbl As ListObject) As Variant
    Dim ws As Worksheet
    Dim nuevoTextBox As Object
    Dim nuevoTextBoxValor As Object
    Dim encabezadoLabel As Object
    Dim i As Integer
    Dim fila As Integer
    Dim Columna As Integer
    Dim topBase As Integer
    Dim leftBase As Integer
    Dim espacioHorizontal As Integer
    Dim espacioVertical As Integer
    Dim Nombres() As String
    Dim Nfilas As Integer
    Dim Ncolum As Integer
    Dim totalColumns As Integer
     ' Variable para el ancho total necesario

    ' Cambiar el color de fondo del formulario
    FormuDatosConex.BackColor = RGB(255, 255, 255) ' Blanco

    ' Crear el encabezado del formulario
    Set encabezadoLabel = FormuDatosConex.Controls.Add("Forms.Label.1", "EncabezadoLabel", True)
    With encabezadoLabel
        .Caption = "Propiedades de Conexiones"
        .Top = 10
        .Left = 20
        .Width = 300
        .Height = 20
        .Font.Size = 12
        .Font.Bold = True
        .Font.Italic = True
    End With

    ' Inicializar configuración
    topBase = encabezadoLabel.Top + encabezadoLabel.Height + 30
    leftBase = 20
    espacioHorizontal = 165 ' Ancho de cada columna
    espacioVertical = 28    ' Alto de cada fila
    Nfilas = 11           ' Número de filas especificado por el usuario (ajustar según necesidad)

    ' Calcular el número total de columnas necesarias
    totalColumns = Int(tbl.ListColumns.Count / Nfilas) ' Número total de columnas (redondeado hacia abajo)
    If tbl.ListColumns.Count Mod Nfilas > 0 Then
        totalColumns = totalColumns + 1 ' Si hay un resto, añadir una columna adicional
    End If

    ' Calcular el ancho total requerido
    totalWidth = leftBase + espacioHorizontal * totalColumns ' 20 es el margen adicional para separación
    


    AnchoMaximoFormuDatosConex = 1000
    AlturaMaximoFormuDatosConex = 800
    ' Ajustar el ancho del formulario según el número de columnas
    'FormuDatosConex.Width = totalWidth

    ' Redimensionar el array de nombres
    ReDim Nombres(1 To tbl.ListColumns.Count)

    ' Recorrer columnas de la tabla
    For i = 1 To tbl.ListColumns.Count
        fila = (i - 1) \ totalColumns ' Calcular la fila actual
        Columna = (i - 1) Mod totalColumns ' Calcular la columna actual

        ' TextBox para el nombre de la columna
        Set nuevoTextBox = FormuDatosConex.Controls.Add("Forms.TextBox.1", "TextBoxNombreColumna" & i, True)
        With nuevoTextBox
            .text = tbl.ListColumns(i).Name
            .Top = topBase + fila * espacioVertical
            .Left = leftBase + Columna * espacioHorizontal
            .Width = 80
            .Height = 25
            .Font.Size = 7
            .BackColor = RGB(92, 125, 156)
            .ForeColor = RGB(255, 255, 255)
            .Font.Bold = True
            .MultiLine = True
            .ScrollBars = fmScrollBarsHorizontal
            .TextAlign = 2
            .Locked = True
        End With

        ' TextBox para el valor
        Set nuevoTextBoxValor = FormuDatosConex.Controls.Add("Forms.TextBox.1", tbl.ListColumns(i).Name, True)
        With nuevoTextBoxValor
            .Top = nuevoTextBox.Top
            .Left = nuevoTextBox.Left + nuevoTextBox.Width + 5
            .Width = 60      ' antes 80
            .Height = 25     ' antes 25
            .Font.Size = 8   ' reducido
            .BackColor = RGB(235, 247, 255)
            .TextAlign = 1
        End With

        ' Guardar nombre en el array
        Nombres(i) = tbl.ListColumns(i).Name
    Next i
    
    ' Calcular el alto total requerido
    totalHeight = 2 * topBase + Nfilas * nuevoTextBox.Height

    ' Devolver array de nombres
    MontarFormulario = Nombres
End Function


Public Sub EscribeFila(Nombres() As String, LR0 As ListRow)
    Dim i As Integer
    Dim nuevoTextBoxValor As Object
    Dim Area As Range
    Dim FilaSeleccionada As Long
    Dim FilaLocalTabla As Long

    ' Escribir los valores en los TextBox correspondientes
    For i = LBound(Nombres) To UBound(Nombres)
    
        Set nuevoTextBoxValor = FormuDatosConex.Controls(Nombres(i))
        'nuevoTextBoxValor.Text = tbl.DataBodyRange.Cells(FilaLocalTabla + 1, i).Value
        
        nuevoTextBoxValor.text = LR0.Range.Cells(1, i).value
    Next i
End Sub

Public Sub VisualizadorLocal()

    Dim ws As Worksheet
    Dim tbl As ListObject
    Dim LR0 As ListRow
    
    Dim NumeAreas As Integer
    Dim NumeFilas As Integer
    Dim Con0 As Integer
    Dim Con1 As Integer
    Dim i As Integer
    Dim j As Integer

    ' Obtener la hoja activa
    Set ws = ActiveSheet

    If ws.ListObjects.Count = 0 Then
        MsgBox "No hay tablas en la hoja activa.", vbExclamation
        Exit Sub
    End If

    ' Obtener la primera tabla en la hoja activa
    Set tbl = ws.ListObjects(1)

    ' Construir formulario y obtener nombres de controles
    NombresControlesCampos = MontarFormulario(tbl)

    ' ============================
    ' Cálculo de áreas y filas
    ' ============================
    NumeAreas = Application.Selection.Areas.Count
    NumeFilas = 0

    For i = 1 To NumeAreas
        NumeFilas = NumeFilas + Application.Selection.Areas(i).Count
    Next i

    ' Redimensionar array
    ReDim MaFilasSelecTabla(0 To NumeFilas - 1)

    ' ============================
    ' Rellenar filas seleccionadas
    ' ============================
    Con0 = 0
    For i = 1 To NumeAreas

        Con1 = 0
        MaFilasSelecTabla(Con0) = _
            Application.Selection.Areas(i).Row - tbl.ListRows(1).Range.Row + 1
        Con0 = Con0 + 1

        For j = 1 To Application.Selection.Areas(i).Count - 1
            MaFilasSelecTabla(Con0) = _
                Application.Selection.Areas(i).Row + Con1 - tbl.ListRows(1).Range.Row + 1
            Con0 = Con0 + 1
            Con1 = Con1 + 1
        Next j

    Next i

    ' ============================
    ' Obtener fila activa de tabla
    ' ============================
    If MaFilasSelecTabla(iFilaSelecTabla) > 0 Then
        Set LR0 = tbl.ListRows(MaFilasSelecTabla(iFilaSelecTabla))
    Else
        MsgBox "La región seleccionada no es válida", vbExclamation
        Exit Sub
    End If

    ' Escribir datos en formulario
    Call EscribeFila(NombresControlesCampos, LR0)

    ' ============================
    ' Protección y visualización
    ' ============================
    Set RangoHojaActiva = ActiveCell
    ws.Range("BL11").Activate
    ws.Protect

    FormuDatosConex.Show vbModeless

End Sub


Sub CrearArchivoTexto()
    Dim ruta As String
    ruta = ThisWorkbook.Path & "/Miguel.txt"
    
    Dim archivoLibre As Integer
    archivoLibre = FreeFile
    
    Open ruta For Output As #archivoLibre
    Print #archivoLibre, "Hola, este es un archivo de texto creado con VBA."
    Print #archivoLibre, "Segunda línea de texto."
    Close #archivoLibre
End Sub

-------------------------------------------------------------------------------
VBA MACRO Hoja37.cls 