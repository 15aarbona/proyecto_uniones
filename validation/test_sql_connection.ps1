<#
Prueba de conexion al SQL Server de perfiles de CODAME.
Pensado para ejecutarse EN UN EQUIPO UNIDO AL DOMINIO TR (ad.tecnicasreunidas.es),
porque el servidor exige autenticacion integrada (Trusted_Connection=True).

Uso (por defecto, misma cadena que lleva CalcCodame.exe hardcodeada):
    powershell -ExecutionPolicy Bypass -File .\test_sql_connection.ps1

Con SQL auth (si IT te da usuario/clave):
    .\test_sql_connection.ps1 -User 'mi_usuario' -Password 'mi_clave'

Otro servidor / BD:
    .\test_sql_connection.ps1 -Server 'TR-SQLISO-YEC01\AMS' -Database 'CONEXIONES'
#>
[CmdletBinding()]
param(
    [string]$Server   = 'TR-SQLISO-YEC01\AMS',
    [string]$Database = 'CONEXIONES',
    [string]$User,
    [string]$Password,
    [int]$TimeoutSeconds = 8
)

$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Data | Out-Null

function Line($t){ Write-Host ("-" * 64); Write-Host $t; Write-Host ("-" * 64) }

$hostOnly = ($Server -split '\\')[0]
$instance = if ($Server -match '\\') { ($Server -split '\\')[1] } else { $null }

Line "ENTORNO LOCAL"
Write-Host "Usuario      : $(whoami)"
Write-Host "Dominio      : $env:USERDOMAIN"
try { Write-Host "Dominio PC   : $((Get-CimInstance Win32_ComputerSystem).Domain)" } catch {}
Write-Host "Servidor SQL : $Server   (host=$hostOnly instancia=$instance)"

Line "RED / RESOLUCION"
try {
    Resolve-DnsName -Name $hostOnly -ErrorAction Stop |
        Where-Object { $_.IPAddress } |
        Select-Object Name, Type, IPAddress | Format-Table -AutoSize | Out-Host
} catch { Write-Host "DNS FAIL: $($_.Exception.Message)" -ForegroundColor Red }

try {
    Test-Connection -ComputerName $hostOnly -Count 2 -ErrorAction Stop |
        Select-Object Address, ResponseTime | Format-Table -AutoSize | Out-Host
} catch { Write-Host "PING FAIL: $($_.Exception.Message)" -ForegroundColor Red }

foreach ($p in 1433, 1434, 14330) {
    $r = Test-NetConnection -ComputerName $hostOnly -Port $p -WarningAction SilentlyContinue
    Write-Host ("TCP {0,-6}: {1}" -f $p, $r.TcpTestSucceeded)
}

Line "CONEXION SQL"
$auth = if ($User) { "User ID=$User;Password=$Password" } else { "Integrated Security=True;Trusted_Connection=True" }
$cs = "Server=$Server;Database=$Database;$auth;Connect Timeout=$TimeoutSeconds;TrustServerCertificate=True"
Write-Host ("Cadena: " + ($cs -replace '(Password=)[^;]*','$1***'))
Write-Host ""

function Get-SqlError($ex) {
    if ($ex -is [System.Management.Automation.ErrorRecord]) { $ex = $ex.Exception }
    $e = $ex
    while ($e.InnerException) { $e = $e.InnerException }
    return $e
}
function Report-SqlError($ex, $ms) {
    $e = Get-SqlError $ex
    if ($e -is [System.Data.SqlClient.SqlException]) {
        Write-Host "FALLO ($ms ms)" -ForegroundColor Red
        Write-Host ("  SQL Number={0} Class={1} State={2} Server={3}" -f $e.Number, $e.Class, $e.State, $e.Server)
        Write-Host ("  Mensaje: {0}" -f $e.Message)
        if ($e.Number -eq 18456) {
            # Sub-estado tipico: identifica la causa exacta
            Write-Host "  Sub-estado 18456 (login):" -ForegroundColor Yellow
            Write-Host "     1/2 = login inexistente o clave incorrecta"
            Write-Host "     5   = usuario no existe"
            Write-Host "     6   = intento con SQL auth sobre login de Windows"
            Write-Host "     7/8 = login deshabilitado / clave incorrecta"
            Write-Host "    11/12 = login valido pero SIN permiso para abrir la BD pedida"
            Write-Host "  -> Si es 11/12: pide a IT que conceda a tu login acceso a '$Database'."
            Write-Host "  -> Si es 5/7/8: usa -User/-Password con un login valido de SQL."
        }
    } else {
        Write-Host "FALLO ($ms ms): $($e.Message)" -ForegroundColor Red
    }
}

# --- Etapa 1: solo login (a 'master'), para separar autenticacion de permisos ---
Line "ETAPA 1 - LOGIN (master)"
$csMaster = "Server=$Server;Database=master;$auth;Connect Timeout=$TimeoutSeconds;TrustServerCertificate=True"
$loginOk = $false
$hasDbAccess = $null
$sw = [Diagnostics.Stopwatch]::StartNew()
try {
    $c = New-Object System.Data.SqlClient.SqlConnection $csMaster
    $c.Open(); $sw.Stop(); $loginOk = $true
    Write-Host ("LOGIN OK en {0} ms" -f $sw.ElapsedMilliseconds) -ForegroundColor Green
    $q = $c.CreateCommand()
    $q.CommandText = @"
SELECT
    @@SERVERNAME AS srv,
    SUSER_SNAME() AS login_name,
    ORIGINAL_LOGIN() AS original_login,
    IS_SRVROLEMEMBER('sysadmin') AS is_sysadmin,
    HAS_DBACCESS('$Database') AS has_db_access
"@
    $rd = $q.ExecuteReader()
    if ($rd.Read()) {
        Write-Host "  @@SERVERNAME      : $($rd['srv'])"
        Write-Host "  Login efectivo    : $($rd['login_name'])"
        Write-Host "  Login original    : $($rd['original_login'])"
        Write-Host "  sysadmin          : $($rd['is_sysadmin'])"
        Write-Host "  HAS_DBACCESS('$Database') : $($rd['has_db_access'])"
        $hasDbAccess = [int]$rd['has_db_access']
    }
    $rd.Close()

    Write-Host "  Bases de datos visibles:"
    $q.CommandText = "SELECT name FROM sys.databases ORDER BY name"
    $rd = $q.ExecuteReader()
    while ($rd.Read()) { Write-Host "    - $($rd['name'])" }
    $rd.Close()
    $c.Close()
}
catch { $sw.Stop(); Report-SqlError $_ $sw.ElapsedMilliseconds }

if (-not $loginOk) {
    Line "RESULTADO"
    Write-Host "FAIL: el login no autentica (revisa identidad/credenciales)." -ForegroundColor Red
    exit 1
}
if ($hasDbAccess -eq 0) {
    Line "RESULTADO"
    Write-Host "FAIL: login correcto pero SIN acceso a la BD '$Database' (HAS_DBACCESS=0)." -ForegroundColor Red
    Write-Host "Pide a IT que conceda acceso a tu login sobre '$Database'." -ForegroundColor Yellow
    exit 1
}

# --- Etapa 2: conexion real a la BD pedida ---
Line "ETAPA 2 - ACCESO A '$Database'"
$ok = $false
$sw = [Diagnostics.Stopwatch]::StartNew()
try {
    $conn = New-Object System.Data.SqlClient.SqlConnection $cs
    $conn.Open()
    $sw.Stop()
    $ok = $true
    Write-Host ("CONEXION OK en {0} ms" -f $sw.ElapsedMilliseconds) -ForegroundColor Green

    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT @@SERVERNAME AS server, DB_NAME() AS db, SUSER_SNAME() AS usr, @@VERSION AS ver"
    $rd = $cmd.ExecuteReader()
    if ($rd.Read()) {
        Write-Host "  @@SERVERNAME : $($rd['server'])"
        Write-Host "  Database     : $($rd['db'])"
        Write-Host "  Login        : $($rd['usr'])"
        Write-Host "  Version      : $(([string]$rd['ver']).Split("`n")[0])"
    }
    $rd.Close()

    # Tabla de perfiles metalicos que usa ConsultaPerfilesSQLServer (heuristica de nombres)
    Line "TABLAS DE PERFILES (candidatas)"
    $cmd.CommandText = @"
SELECT TOP 20 TABLE_SCHEMA, TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME LIKE '%perfil%' OR TABLE_NAME LIKE '%profile%'
   OR TABLE_NAME LIKE '%section%' OR TABLE_NAME LIKE '%acero%'
ORDER BY TABLE_NAME;
"@
    $rd = $cmd.ExecuteReader()
    $found = 0
    while ($rd.Read()) { $found++; Write-Host ("  {0}.{1}" -f $rd['TABLE_SCHEMA'], $rd['TABLE_NAME']) }
    $rd.Close()
    if ($found -eq 0) { Write-Host "  (ninguna; revisa el nombre real de la tabla de perfiles)" -ForegroundColor Yellow }

    $conn.Close()
}
catch {
    $sw.Stop()
    Report-SqlError $_ $sw.ElapsedMilliseconds
}

Line "RESULTADO"
if ($ok) { Write-Host "PASS: SQL accesible con esta identidad." -ForegroundColor Green; exit 0 }
else     { Write-Host "FAIL: no se pudo validar contra el SQL." -ForegroundColor Red;  exit 1 }
