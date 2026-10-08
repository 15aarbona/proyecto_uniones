- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
None
+----------+--------------------+---------------------------------------------+
|Type      |Keyword             |Description                                  |
+----------+--------------------+---------------------------------------------+
|AutoExec  |Workbook_Open       |Runs when the Excel Workbook is opened       |
|AutoExec  |ListBox1_Click      |Runs when the file is opened and ActiveX     |
|          |                    |objects trigger events                       |
|AutoExec  |Worksheet_Change    |Runs when the file is opened and ActiveX     |
|          |                    |objects trigger events                       |
|Suspicious|Environ             |May read system environment variables        |
|Suspicious|Open                |May open a file                              |
|Suspicious|Output              |May write to a file (if combined with Open)  |
|Suspicious|Print #             |May write to a file (if combined with Open)  |
|Suspicious|CopyFile            |May copy a file                              |
|Suspicious|Shell               |May run an executable file or a system       |
|          |                    |command                                      |
|Suspicious|vbMinimizedNoFocus  |May run an executable file or a system       |
|          |                    |command                                      |
|Suspicious|Call                |May call a DLL using Excel 4 Macros (XLM/XLF)|
|Suspicious|Application.Visible |May hide the application                     |
|Suspicious|CreateObject        |May create an OLE object                     |
|Suspicious|ExecuteExcel4Macro  |May run an Excel 4 Macro (aka XLM/XLF) from  |
|          |                    |VBA                                          |
|Suspicious|MSXML2.XMLHTTP      |May download files from the Internet         |
|Suspicious|MSXML2.ServerXMLHTTP|May download files from the Internet         |
|Suspicious|Chr                 |May attempt to obfuscate specific strings    |
|          |                    |(use option --deobf to deobfuscate)          |
|Suspicious|Hex Strings         |Hex-encoded strings were detected, may be    |
|          |                    |used to obfuscate strings (option --decode to|
|          |                    |see all)                                     |
|Suspicious|Base64 Strings      |Base64-encoded strings were detected, may be |
|          |                    |used to obfuscate strings (option --decode to|
|          |                    |see all)                                     |
|IOC       |http://10.97.116.84:|URL                                          |
|          |8080                |                                             |
|IOC       |10.97.116.84        |IPv4 address                                 |
|IOC       |SCS_FORM_VB.exe     |Executable file name                         |
|IOC       |BDCONEXIONES.exe    |Executable file name                         |
|IOC       |SCS_CONNEXTOR.exe   |Executable file name                         |
|IOC       |CalcCodame.exe      |Executable file name                         |
|IOC       |CalcExcelEngine.exe |Executable file name                         |
|IOC       |CalcMathcad.exe     |Executable file name                         |
|IOC       |ChequeoGeoconex.exe |Executable file name                         |
|IOC       |InterfazFormuExcel.e|Executable file name                         |
|          |xe                  |                                             |
|Suspicious|VBA Stomping        |VBA Stomping was detected: the VBA source    |
|          |                    |code and P-code are different, this may have |
|          |                    |been used to hide malicious code             |
+----------+--------------------+---------------------------------------------+
VBA Stomping detection is experimental: please report any false positive/negative at https://github.com/decalage2/oletools/issues
