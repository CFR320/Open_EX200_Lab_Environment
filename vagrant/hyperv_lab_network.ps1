param(
    [Parameter(Mandatory = $true)]
    [Guid] $VMId
)

$ErrorActionPreference = "Stop"
$switchName = "ex200-lab"
$adapterName = "EX200 Lab"
$hostAdapterAlias = "vEthernet ($switchName)"

$labSwitch = Get-VMSwitch -Name $switchName -ErrorAction SilentlyContinue
if (-not $labSwitch) {
    New-VMSwitch -Name $switchName -SwitchType Internal | Out-Null
}

$hostAddress = Get-NetIPAddress -InterfaceAlias $hostAdapterAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -eq "172.25.250.1" }
if (-not $hostAddress) {
    New-NetIPAddress -InterfaceAlias $hostAdapterAlias -IPAddress "172.25.250.1" -PrefixLength 24 | Out-Null
}

$vm = Get-VM -Id $VMId
$labAdapter = Get-VMNetworkAdapter -VM $vm -Name $adapterName -ErrorAction SilentlyContinue
if (-not $labAdapter) {
    Add-VMNetworkAdapter -VM $vm -Name $adapterName -SwitchName $switchName
} elseif ($labAdapter.SwitchName -ne $switchName) {
    Connect-VMNetworkAdapter -VMNetworkAdapter $labAdapter -SwitchName $switchName
}
