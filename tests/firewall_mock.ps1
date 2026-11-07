# In-memory test double: never invokes Windows firewall cmdlets.
param([string]$ConfigureFile, [string]$ReadFile)
$ErrorActionPreference = 'Stop'
$script:rules = @{}
$script:blockedPolicy = $false
$script:removed = @()
function Get-NetFirewallRule {
    [CmdletBinding()] param([string[]]$Name, [string]$PolicyStore, [Parameter(ValueFromPipeline)]$InputObject)
    process {
        if ($InputObject) { $script:rules[$InputObject.Name] }
        elseif ($Name) { foreach ($key in $Name) { if ($script:rules.ContainsKey($key)) { $script:rules[$key] } } }
        else { $script:rules.Values }
    }
}
function New-NetFirewallRule {
    [CmdletBinding()] param($Name, $DisplayName, $Group, $Program, $Direction, $Action, $Enabled,
        $Protocol, $LocalPort, $RemoteAddress, $Profile, $EdgeTraversalPolicy, $PolicyStore)
    if ($PolicyStore -ne 'PersistentStore') { throw 'Unexpected writable store' }
    $script:rules[$Name] = [pscustomobject]@{Name=$Name; Program=$Program; Direction=$Direction;
        Action=$Action; Enabled=$Enabled; Protocol=$Protocol; LocalPort=$LocalPort;
        RemoteAddress=$RemoteAddress; Profile=$Profile; EdgeTraversalPolicy=$EdgeTraversalPolicy}
}
function Set-NetFirewallRule {
    [CmdletBinding()] param($Name, $Program, $Direction, $Action, $Enabled,
        $Protocol, $LocalPort, $RemoteAddress, $Profile, $EdgeTraversalPolicy, $PolicyStore)
    New-NetFirewallRule @PSBoundParameters
}
function Remove-NetFirewallRule {
    [CmdletBinding()] param($Name, $PolicyStore)
    if ($PolicyStore -ne 'PersistentStore') { throw 'Unexpected removal store' }
    $script:removed += $Name
    $script:rules.Remove($Name)
}
function Get-NetFirewallApplicationFilter {
    [CmdletBinding()] param($PolicyStore, [Parameter(ValueFromPipeline)]$InputObject)
    process { if ($InputObject) { $InputObject } else { $script:rules.Values } }
}
function Get-NetFirewallAddressFilter {
    [CmdletBinding()] param([Parameter(ValueFromPipeline)]$InputObject)
    process { $InputObject }
}
function Get-NetFirewallPortFilter {
    [CmdletBinding()] param([Parameter(ValueFromPipeline)]$InputObject)
    process { $InputObject }
}
function Get-NetConnectionProfile {
    [pscustomobject]@{NetworkCategory='Public'}
}
function Get-NetFirewallProfile {
    param($PolicyStore)
    [pscustomobject]@{Name='Public'; Enabled='True'; AllowInboundRules='True'; AllowLocalFirewallRules=([string](-not $script:blockedPolicy))}
    # A policy on an inactive profile must not prevent this local setup.
    [pscustomobject]@{Name='Domain'; Enabled='True'; AllowInboundRules='False'; AllowLocalFirewallRules='False'}
}
function Assert($condition, $description) { if (-not $condition) { throw $description } }

$configureText = Get-Content -LiteralPath $ConfigureFile -Raw
$readText = Get-Content -LiteralPath $ReadFile -Raw
# Fail closed if generated scripts ever reference an unmocked network cmdlet.
foreach ($source in @($configureText, $readText)) {
    $parseErrors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseInput($source, [ref]$null, [ref]$parseErrors)
    Assert ($parseErrors.Count -eq 0) 'PowerShell syntax errors'
    foreach ($command in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)) {
        $name = $command.GetCommandName()
        if ($name -match 'NetFirewall|NetConnection') {
            Assert ((Get-Command $name).CommandType -eq 'Function') ('Unmocked cmdlet: ' + $name)
        }
    }
}
$configure = [scriptblock]::Create($configureText)
$read = [scriptblock]::Create($readText)
$initial = & $read | ConvertFrom-Json
Assert (-not $initial.configured) 'Empty rules reported ready'
# Read script assigns the exact quoted app path and names in its scope; capture independently.
$variables = [scriptblock]::Create(($configureText -split 'foreach')[0])
. $variables
New-NetFirewallRule -Name native-block -Program $program -Direction Inbound -Action Block -Enabled True -PolicyStore PersistentStore
New-NetFirewallRule -Name other-app -Program 'C:\Other\Other.exe' -Direction Inbound -Action Block -Enabled True -PolicyStore PersistentStore
New-NetFirewallRule -Name outbound-block -Program $program -Direction Outbound -Action Block -Enabled True -PolicyStore PersistentStore
& $configure
Assert ($script:removed.Count -eq 1 -and $script:removed[0] -eq 'native-block') 'Removed unrelated rule'
Assert ($script:rules.ContainsKey('other-app') -and $script:rules.ContainsKey('outbound-block')) 'Lost unrelated rules'
$report = & $read | ConvertFrom-Json
Assert ($report.configured -and $report.app_blocks -eq 0) 'New local rules not ready'
Assert ($script:rules[$tcpName].RemoteAddress -eq 'LocalSubnet') 'Missing LAN scope'
Assert ($script:rules[$udpName].LocalPort -eq '5353') 'Wrong discovery port'
Assert ($script:rules[$tcpName].Program -eq "C:\Users\O'Neil\DnDLocal.exe") 'Quoted program path changed'
& $configure
Assert ($script:rules.Count -eq 4) 'Repeated setup duplicated rules'
$script:rules[$tcpName].Enabled = 'False'
Assert (-not ((& $read | ConvertFrom-Json).configured)) 'Disabled rule accepted'
$script:rules[$tcpName].Enabled = 'True'
$script:rules[$udpName].LocalPort = '9999'
Assert (-not ((& $read | ConvertFrom-Json).configured)) 'Wrong port accepted'
& $configure
Assert ((& $read | ConvertFrom-Json).configured) 'Existing rule repair failed'
$script:blockedPolicy = $true
$report = & $read | ConvertFrom-Json
Assert (-not $report.configured -and $report.policy_blocks -eq 1) 'Active policy block ignored'
$script:blockedPolicy = $false
New-NetFirewallRule -Name policy-app-block -Program $program -Direction Inbound -Action Block -Enabled True -PolicyStore PersistentStore
$report = & $read | ConvertFrom-Json
Assert (-not $report.configured -and $report.app_blocks -eq 1) 'Effective application block ignored'
'PASS: syntax, exact app, LAN scope, quote escaping, idempotency, rule repair, policy and block diagnosis'
