- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

Public NombreValor As String
Public TablaValor As String
Public NombreHojaExcel As String
Public LibroExcel As Workbook
Public RangoNombre As Range
Public RangoTabla As Range

Public AddressNombreEscritura As String
Public AddressNombreLectura As String
Public AddressTablaEscritura As String
Public AddressTablaLectura As String

Property Get HojaAddressNomEscri() As String

    HojaAddressNomEscri = NombreHojaExcel & " " & AddressNombreEscritura

End Property

Property Get HojaAddressNomLectu() As String

    HojaAddressNomLectu = NombreHojaExcel & " " & AddressNombreLectura

End Property

Property Get HojaAddressTablaEscri() As String

    HojaAddressTablaEscri = NombreHojaExcel & " " & AddressTablaEscritura

End Property

Property Get HojaAddressTablaLectu() As String

    HojaAddressTablaLectu = NombreHojaExcel & " " & AddressTablaLectura

End Property

Public Sub DatosNombreExcel()

Dim hoja As Worksheet

Set RangoNombre = LibroExcel.Names(NombreValor).RefersToRange
Set hoja = RangoNombre.Worksheet

NombreHojaExcel = hoja.Name

AddressNombreEscritura = Application.WorksheetFunction.Substitute(RangoNombre.Address, "$", "")
AddressNombreLectura = Application.WorksheetFunction.Substitute(AddFilaARango(RangoNombre), "$", "")

End Sub

Public Sub DatosTablaExcel()

Dim Rango As Range, hoja As Worksheet

Set RangoTabla = LibroExcel.Worksheets(NombreHojaExcel).ListObjects(TablaValor).Range
Set hoja = RangoTabla.Worksheet

AddressTablaLectura = Application.WorksheetFunction.Substitute(RangoTabla.Address, "$", "")
AddressTablaEscritura = Application.WorksheetFunction.Substitute(DeleteFilaARango(RangoTabla), "$", "")

Set RangoTabla = LibroExcel.Worksheets(NombreHojaExcel).Range(AddressTablaEscritura)

End Sub

Public Function AddFilaARango(Rango As Range) As String

Dim RangoModi As Range
Dim FilaIni As Integer, FilaFinal As Integer, ColuIni As Integer, ColuFinal As Integer

ColuIni = Rango.column
ColuFinal = Rango.column + Rango.Columns.Count - 1
FilaIni = Rango.Row
FilaFinal = Rango.Row + Rango.Rows.Count - 1

Set RangoModi = Range(Cells(FilaIni - 1, ColuIni), Cells(FilaFinal, ColuFinal))

AddFilaARango = RangoModi.Address

End Function

Public Function DeleteFilaARango(Rango As Range) As String

Dim RangoModi As Range
Dim FilaIni As Integer, FilaFinal As Integer, ColuIni As Integer, ColuFinal As Integer

ColuIni = Rango.column
ColuFinal = Rango.column + Rango.Columns.Count - 1
FilaIni = Rango.Row
FilaFinal = Rango.Row + Rango.Rows.Count - 1

Set RangoModi = Range(Cells(FilaIni + 1, ColuIni), Cells(FilaFinal, ColuFinal))

DeleteFilaARango = RangoModi.Address

End Function
-------------------------------------------------------------------------------
VBA MACRO ClaseNombreBD.cls 