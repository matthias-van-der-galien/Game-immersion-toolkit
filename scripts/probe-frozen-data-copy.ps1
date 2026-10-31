param([Parameter(Mandatory=$true)][string]$RuntimeRoot,
      [Parameter(Mandatory=$true)][string]$Provenance,
      [ValidateSet('authored-data-copy','authored-data-copy-resume','authored-data-copy-wal','authored-data-copy-grammar')][string]$ProbeCase='authored-data-copy',
      [string]$Output=(Join-Path $PSScriptRoot '../output/checks/r19-frozen-data-copy.json'))
$ErrorActionPreference='Stop'
if ($ProbeCase -cnotin @('authored-data-copy','authored-data-copy-resume','authored-data-copy-wal','authored-data-copy-grammar')) { throw 'Unknown fixed authored data-copy case.' }
if ($ProbeCase -ceq 'authored-data-copy-resume' -and -not $PSBoundParameters.ContainsKey('Output')) {
    $Output=Join-Path $PSScriptRoot '../output/checks/r19-frozen-data-copy-resume.json'
}
if ($ProbeCase -ceq 'authored-data-copy-wal' -and -not $PSBoundParameters.ContainsKey('Output')) {
    $Output=Join-Path $PSScriptRoot '../output/checks/r19-frozen-data-copy-wal.json'
}
if ($ProbeCase -ceq 'authored-data-copy-grammar' -and -not $PSBoundParameters.ContainsKey('Output')) {
    $Output=Join-Path $PSScriptRoot '../output/checks/r19-frozen-data-copy-grammar.json'
}
Remove-Item -LiteralPath $Output -Force -ErrorAction SilentlyContinue
if ($PSVersionTable.PSEdition -ne 'Core' -or -not $IsWindows) { throw 'The authored data-copy harness requires Windows PowerShell 7 on the build host.' }
. (Join-Path $PSScriptRoot 'r19-runtime-inventory.ps1')
$slotSourceOperation=Join-Path $PSScriptRoot 'companion-runtime.ps1'
foreach ($selection in @(
    @{file='probe-frozen-slots.ps1';names=@('Assert-SlotEntryName','Assert-SlotInventory','Invoke-SlotLeaseObservation')})) {
    $tokens=$null; $parseErrors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $selection.file),[ref]$tokens,[ref]$parseErrors)
    if ($parseErrors) { throw 'Existing fixed data-copy harness operation could not be parsed.' }
    foreach ($name in $selection.names) {
        $definition=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
        if (-not $definition) { throw 'Missing existing fixed data-copy harness operation.' }
        . ([scriptblock]::Create($definition.Extent.Text))
    }
}

function Start-DataCopyOwner {
    # This fixed owner retains C1's isolated environment and host entrypoint.
    # Its local I/O policy must not inherit unbounded C1 capture tasks.
    $info=[Diagnostics.ProcessStartInfo]::new()
    $info.FileName=Join-Path $RuntimeRoot 'ProxyTranscriptRuntime.exe'
    $info.Arguments='--runtime-probe host'
    $info.UseShellExecute=$false
    $info.RedirectStandardOutput=$info.RedirectStandardError=$info.RedirectStandardInput=$true
    $info.WorkingDirectory=$temporary
    $info.Environment.Clear()
    foreach ($name in @('WINDIR','SystemRoot','COMSPEC','PATHEXT')) {
        if ([Environment]::GetEnvironmentVariable($name)) { $info.Environment[$name]=[Environment]::GetEnvironmentVariable($name) }
    }
    $info.Environment['PATH']="$env:WINDIR/System32;$env:WINDIR"
    foreach ($name in @('TEMP','TMP','USERPROFILE','HOME','LOCALAPPDATA','APPDATA')) { $info.Environment[$name]=Join-Path $temporary 'empty-host' }
    foreach ($name in $roots.Keys) { $info.Environment[$name]=$roots[$name] }
    $info.Environment['PROXY_TRANSCRIPT_STANDBY']='1'
    $info.Environment['PYINSTALLER_RESET_ENVIRONMENT']='1'
    $process=[Diagnostics.Process]::new();$process.StartInfo=$info
    if (-not $process.Start()) { throw 'Fixed authored data-copy owner did not start.' }
    $owned.Add($process)
    $null=$process.Handle
    # CopyToAsync uses only this fixed buffer; no stderr string/bytes/count/hash
    # are retained or published. Never read through the text wrappers as well.
    $script:stderrDiscard=$process.StandardError.BaseStream.CopyToAsync([IO.Stream]::Null,4096)
    $script:controlReader=New-DataCopyControlReader $process.StandardOutput.BaseStream $script:stderrDiscard
    $process.StandardInput.WriteLine($ProbeCase);$process.StandardInput.Flush()
    return $process
}
function New-DataCopyControlReader([IO.Stream]$Stream, [Threading.Tasks.Task]$Discard) {
    return [pscustomobject]@{stream=$Stream;discard=$Discard;buffer=[byte[]]::new(4096);line=[byte[]]::new(8192);
        offset=0;count=0;pending=$null;fault='none';last_line_bytes=0}
}
function Read-DataCopyControlLine($Reader, [int]$TimeoutMilliseconds=120000, [bool]$AllowEof=$false) {
    if ($Reader.fault -cne 'none') { throw 'The authored control reader is already unavailable.' }
    $timer=[Diagnostics.Stopwatch]::StartNew();$used=0
    try {
        while ($true) {
            if ($Reader.discard.IsFaulted -or $Reader.discard.IsCanceled) {
                $Reader.fault='stderr-unavailable';throw 'The authored stderr discard is unavailable.'
            }
            if ($Reader.offset -eq $Reader.count) {
                # There is exactly one pending read and one foreground consumer.
                # On a fault/timeout its state is retained and never rearmed.
                if ($null -eq $Reader.pending) { $Reader.pending=$Reader.stream.ReadAsync($Reader.buffer,0,$Reader.buffer.Length) }
                $remaining=$TimeoutMilliseconds-[int]$timer.ElapsedMilliseconds
                if ($remaining -le 0) { $Reader.fault='control-deadline';throw 'The authored control deadline expired.' }
                if (-not $Reader.pending.Wait([Math]::Min(100,$remaining))) { continue }
                $count=$Reader.pending.GetAwaiter().GetResult()
                if ($count -lt 0 -or $count -gt $Reader.buffer.Length) { throw 'Invalid authored control read result.' }
                $Reader.pending=$null;$Reader.offset=0;$Reader.count=$count
                if ($count -eq 0) {
                    if ($AllowEof -and $used -eq 0) { return $null }
                    $Reader.fault='control-eof';throw 'Authored control ended before a complete line.'
                }
            }
            while ($Reader.offset -lt $Reader.count) {
                $byte=$Reader.buffer[$Reader.offset];$Reader.offset++
                if ($byte -eq 10) {
                    $Reader.last_line_bytes=$used
                    if ($used -gt 0 -and $Reader.line[$used-1] -eq 13) { $used-- }
                    try { return [Text.UTF8Encoding]::new($false,$true).GetString($Reader.line,0,$used) }
                    catch { $Reader.fault='control-invalid-utf8';throw 'Authored control UTF8 is invalid.' }
                }
                if ($used -eq $Reader.line.Length) { $Reader.fault='control-overflow';throw 'Authored control exceeded its byte limit.' }
                $Reader.line[$used]=$byte;$used++
            }
        }
    } catch {
        if ($Reader.fault -ceq 'none') { $Reader.fault='control-reader-unavailable' }
        throw 'Bounded authored control is unavailable.'
    }
}

function Get-DataCopyRoots([string]$TemporaryRoot, [ValidateSet('authored-data-copy','authored-data-copy-resume','authored-data-copy-wal','authored-data-copy-grammar')][string]$Case='authored-data-copy') {
    $private=Join-Path (Join-Path $TemporaryRoot 'empty-host') $Case
    return @{PROXY_TRANSCRIPT_SETTINGS_ROOT=$private;PROXY_TRANSCRIPT_DATA_ROOT=(Join-Path $private 'data-v1');
        PROXY_TRANSCRIPT_CACHE_ROOT=(Join-Path $private 'cache-v1');PROXY_TRANSCRIPT_WORK_ROOT=(Join-Path $private 'cache-v1/work');
        PROXY_TRANSCRIPT_TOOL_ROOT=(Join-Path $private 'tools-v1');PROXY_TRANSCRIPT_STATE_ROOT=(Join-Path $private 'host-v1');
        PROXY_TRANSCRIPT_DEFAULT_EXPORT_ROOT=(Join-Path $private 'exports')}
}
function Assert-DataCopyPortsFree {
    foreach ($port in @(3000,8766)) {
        $listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$port)
        try { $listener.Start() } finally { $listener.Stop() }
    }
}
function Assert-DataCopyLeases([ValidateSet('open','blocked')][string]$Expected) {
    foreach ($path in $leasePaths) {
        if ((Invoke-SlotLeaseObservation $path) -ne $Expected) { throw 'Authored data-copy native exclusion differs.' }
    }
    if ((Invoke-SlotLeaseObservation $legacyRoot 'legacy-source') -ne $Expected) { throw 'The actual source operation exclusion differs.' }
    if ($Expected -eq 'blocked') { $script:sourceBlocks++ }
}
function Read-DataCopyEvent([string]$Phase) {
    if ($script:ProbeCase -cnotin @('authored-data-copy','authored-data-copy-resume','authored-data-copy-wal','authored-data-copy-grammar')) { throw 'Unknown fixed authored data-copy case.' }
    $resumeCase=$script:ProbeCase -ceq 'authored-data-copy-resume'
    $walCase=$script:ProbeCase -ceq 'authored-data-copy-wal'
    $grammarCase=$script:ProbeCase -ceq 'authored-data-copy-grammar'
    if ($Phase -ceq 'copy-interrupted' -and -not $resumeCase) { throw 'Only the fixed resume case can observe an interruption.' }
    if ($Phase -ceq 'wal-set-observed' -and -not $walCase) { throw 'Only the fixed WAL case can observe a retained WAL set.' }
    if ($Phase -ceq 'grammar-written' -and -not $grammarCase) { throw 'Only the fixed grammar case can observe a populated override.' }
    $line=Read-DataCopyControlLine $script:controlReader
    if (-not $line) { throw 'Authored data-copy event is unavailable.' }
    $value=$line | ConvertFrom-Json
    $keys=@('schema','kind','case','phase','status','failure','source_commit','build_id','generation',
        'writers_created','writers_resumed','writers_signaled','strict_drains','copy_verification','source_bytes',
        'source_logical','wal_files','shm_files','old_barrier_refused','api_external_side_effects','sqlite',
        'native_owned_process_tree','writer_console_mode','authority','production_activation','target_activation',
        'r19_complete','keeper_loss','dynamic_writer_admission','warm_routing','credentials','browser','installer')
    if ($resumeCase) { $keys+=@('scope','copy_attempts','authored_interruptions','partial_completed_files',
        'partial_revalidations','same_plan_barrier_generation','copy_resumed') }
    if ($walCase) { $keys+=@('scope','sqlite_policy','sqlite_version','sqlite_version_scope',
        'transcript_wal_bytes','transcript_shm_bytes','wal_set','wal_dependency') }
    if ($grammarCase) { $keys+=@('scope','reading_transport','grammar_credential_fixture','grammar_baseline',
        'unknown_grammar_rule','grammar_written','grammar_snapshot','grammar_restarted','grammar_override_rows') }
    $schema=if ($grammarCase) {'proxy-r19-frozen-data-copy-grammar-probe-v1'} elseif ($walCase) {'proxy-r19-frozen-data-copy-wal-probe-v1'} elseif ($resumeCase) {'proxy-r19-frozen-data-copy-resume-probe-v1'} else {'proxy-r19-frozen-data-copy-probe-v1'}
    if ($null -eq $value -or @(Compare-Object $keys @($value.PSObject.Properties.Name) -CaseSensitive).Count -or
        $value.schema -cne $schema -or $value.kind -cne 'data-copy' -or
        $value.case -cne $script:ProbeCase -or $value.source_commit -cne $proof.source_commit -or
        $value.build_id -cne $proof.build_id -or $value.api_external_side_effects -cne 'mocked' -or
        $value.sqlite -cne 'real' -or $value.native_owned_process_tree -cne 'real' -or
        $value.writer_console_mode -cne 'detached-process' -or
        $value.authority -cne 'retained-creation-objects-and-typed-barrier' -or
        $value.production_activation -isnot [bool] -or $value.production_activation -ne $false -or
        $value.target_activation -isnot [bool] -or $value.target_activation -ne $false -or
        $value.r19_complete -isnot [bool] -or $value.r19_complete -ne $false -or
        $value.old_barrier_refused -isnot [bool] -or $value.keeper_loss -cne 'unavailable' -or
        $value.dynamic_writer_admission -cne 'unavailable' -or $value.warm_routing -cne 'unavailable' -or
        $value.credentials -cne 'not-accessed' -or $value.browser -cne 'not-run' -or $value.installer -cne 'not-built') {
        throw 'Authored data-copy event identity or scope differs.'
    }
    foreach ($name in @('schema','kind','case','phase','status','failure','source_commit','build_id',
        'copy_verification','source_bytes','source_logical','api_external_side_effects','sqlite','native_owned_process_tree',
        'writer_console_mode','authority','keeper_loss','dynamic_writer_admission','warm_routing','credentials','browser','installer')) {
        if ($value.$name -isnot [string]) { throw 'Authored data-copy event string is unavailable.' }
    }
    foreach ($name in @('generation','writers_created','writers_resumed','writers_signaled','strict_drains','wal_files','shm_files')) {
        if (($value.$name -isnot [int] -and $value.$name -isnot [long]) -or $value.$name -lt 0 -or $value.$name -gt 4) {
            throw 'Authored data-copy event count differs.'
        }
    }
    if ($value.generation -gt 2 -or $value.strict_drains -gt 2 -or
        $value.writers_created -gt (2*$value.generation) -or
        $value.writers_resumed -gt $value.writers_created -or $value.writers_signaled -gt $value.writers_created -or
        $value.wal_files -gt 3 -or $value.shm_files -gt 3 -or
        $value.copy_verification -cnotin @('not-run','passed') -or
        $value.source_bytes -cnotin @('not-run','preserved-before-resume') -or
        $value.source_logical -cnotin @('not-run','passed')) { throw 'Authored data-copy result differs.' }
    if ($resumeCase) {
        if ($value.scope -isnot [string] -or $value.scope -cne 'authored-transcript-interrupted-copy-resume-with-living-coordinator' -or
            $value.same_plan_barrier_generation -isnot [bool] -or $value.copy_resumed -isnot [bool]) {
            throw 'Authored copy-resume scope differs.'
        }
        foreach ($name in @('copy_attempts','authored_interruptions','partial_completed_files','partial_revalidations')) {
            if (($value.$name -isnot [int] -and $value.$name -isnot [long]) -or $value.$name -lt 0 -or $value.$name -gt 2) {
                throw 'Authored copy-resume count differs.'
            }
        }
        if ($value.authored_interruptions -gt 1 -or $value.partial_completed_files -gt 1) { throw 'Authored interruption count differs.' }
    }
    if ($walCase) {
        foreach ($name in @('scope','sqlite_policy','sqlite_version','sqlite_version_scope','wal_set','wal_dependency')) {
            if ($value.$name -isnot [string]) { throw 'Authored WAL string is unavailable.' }
        }
        if ($value.scope -cne 'authored-transcript-retained-wal-copy-with-living-coordinator' -or
            $value.sqlite_policy -cne 'no-checkpoint-on-close-per-open-readback' -or
            $value.sqlite_version_scope -cne 'frozen-coordinator' -or
            $value.sqlite_version -cnotmatch '\A[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}\z' -or
            $value.wal_set -cnotin @('not-run','nonempty-after-retained-signals') -or
            $value.wal_dependency -cnotin @('not-run','main-only-false-full-set-true')) { throw 'Authored WAL scope differs.' }
        foreach ($name in @('transcript_wal_bytes','transcript_shm_bytes')) {
            if (($value.$name -isnot [int] -and $value.$name -isnot [long]) -or $value.$name -lt 0 -or $value.$name -gt 8388608) {
                throw 'Authored WAL byte bound differs.'
            }
        }
    }
    if ($grammarCase) {
        foreach ($name in @('scope','reading_transport','grammar_credential_fixture','grammar_baseline',
            'unknown_grammar_rule','grammar_written','grammar_snapshot','grammar_restarted')) {
            if ($value.$name -isnot [string]) { throw 'Authored grammar string is unavailable.' }
        }
        if ($value.scope -cne 'authored-populated-local-grammar-copy-with-living-coordinator' -or
            $value.reading_transport -cne 'fixed-mock-settings-analysis-only' -or
            $value.grammar_credential_fixture -cne 'in-memory-noncredential' -or
            $value.grammar_baseline -cnotin @('not-run','zero-without-local-override') -or
            $value.unknown_grammar_rule -cnotin @('not-run','rejected-404') -or
            $value.grammar_written -cnotin @('not-run','four-with-local-override') -or
            $value.grammar_snapshot -cnotin @('not-run','one-scoped-choice-four') -or
            $value.grammar_restarted -cnotin @('not-run','four-with-local-override') -or
            ($value.grammar_override_rows -isnot [int] -and $value.grammar_override_rows -isnot [long]) -or
            $value.grammar_override_rows -lt 0 -or $value.grammar_override_rows -gt 1) { throw 'Authored grammar scope differs.' }
    }
    $failures=@('fixture-unavailable','setup-close-unconfirmed','setup-still-open','cohort-unconfirmed',
        'owned-host-unconfirmed','copy-refused','copy-result-unconfirmed','schema-unconfirmed','authored-rows-differ',
        'pointer-changed','source-changed','control-unavailable','control-invalid','lease-release-unconfirmed',
        'interrupted-copy-unconfirmed','unexpected-data-copy-failure')
    if ($walCase) { $failures+=@('wal-set-unavailable','wal-dependency-unconfirmed',
        'wal-verification-cleanup-unconfirmed','sqlite-version-unavailable') }
    if ($grammarCase) { $failures+=@('grammar-choice-unconfirmed','wal-verification-cleanup-unconfirmed') }
    if ($value.phase -ceq 'recovery-required' -and $value.status -ceq 'failed' -and $value.failure -cin $failures) {
        $script:failureCategory=$value.failure
        throw 'Authored data-copy owner requires recovery.'
    }
    # Exact fixed progression. None of these observations itself mints a barrier.
    $expected=switch ($Phase) {
        'setup-closed' { @(0,0,0,0,0) }
        'favorite-written' { @(1,2,2,0,0) }
        'grammar-written' { @(1,2,2,0,0) }
        'strict-drain-complete' { @(1,2,2,0,1) }
        'writers-signaled' { @(1,2,2,2,1) }
        'wal-set-observed' { @(1,2,2,2,1) }
        'copy-progress' { @(1,2,2,2,1) }
        'copy-interrupted' { @(1,2,2,2,1) }
        'copy-verified' { @(1,2,2,2,1) }
        'source-resumed' { @(2,4,4,2,1) }
        'final-strict-drain-complete' { @(2,4,4,2,2) }
        'final-writers-signaled' { @(2,4,4,4,2) }
        'released' { @(2,4,4,4,2) }
        default { throw 'Unknown fixed authored data-copy phase.' }
    }
    $actual=@($value.generation,$value.writers_created,$value.writers_resumed,$value.writers_signaled,$value.strict_drains)
    if ($value.phase -cne $Phase -or $value.failure -cne 'none' -or
        $value.status -cne $(if ($Phase -eq 'released') {'passed'} else {'observing'}) -or
        @(Compare-Object $expected $actual -SyncWindow 0).Count) { throw 'Authored data-copy lifecycle differs.' }
    $verified=$Phase -in @('copy-verified','source-resumed','final-strict-drain-complete','final-writers-signaled','released')
    $resumed=$Phase -in @('source-resumed','final-strict-drain-complete','final-writers-signaled','released')
    if ($value.copy_verification -cne $(if ($verified) {'passed'} else {'not-run'}) -or
        $value.source_bytes -cne $(if ($verified) {'preserved-before-resume'} else {'not-run'}) -or
        $value.source_logical -cne $(if ($resumed) {'passed'} else {'not-run'}) -or
        $value.old_barrier_refused -ne $resumed -or (-not $verified -and ($value.wal_files -ne 0 -or $value.shm_files -ne 0))) {
        throw 'Authored data-copy verification order differs.'
    }
    if ($resumeCase) {
        $partial=$Phase -ceq 'copy-interrupted' -or $verified
        $attempts=if ($verified) {2} elseif ($partial -or $Phase -ceq 'copy-progress') {1} else {0}
        $revalidations=if ($verified) {2} elseif ($partial) {1} else {0}
        if ($value.copy_attempts -ne $attempts -or $value.authored_interruptions -ne [int]$partial -or
            $value.partial_completed_files -ne [int]$partial -or $value.partial_revalidations -ne $revalidations -or
            $value.same_plan_barrier_generation -ne $partial -or $value.copy_resumed -ne $verified) {
            throw 'Authored copy-resume verification order differs.'
        }
    }
    if ($walCase) {
        $walObserved=$verified -or $Phase -cin @('wal-set-observed','copy-progress')
        if ($value.wal_set -cne $(if ($walObserved) {'nonempty-after-retained-signals'} else {'not-run'}) -or
            $value.wal_dependency -cne $(if ($verified) {'main-only-false-full-set-true'} else {'not-run'}) -or
            ($walObserved -and ($value.transcript_wal_bytes -le 32 -or $value.transcript_shm_bytes -le 0)) -or
            (-not $walObserved -and ($value.transcript_wal_bytes -ne 0 -or $value.transcript_shm_bytes -ne 0)) -or
            ($verified -and ($value.wal_files -lt 1 -or $value.shm_files -lt 1))) { throw 'Authored WAL verification order differs.' }
    }
    if ($grammarCase) {
        $written=$Phase -cnotin @('setup-closed','favorite-written')
        if ($value.grammar_baseline -cne $(if ($written) {'zero-without-local-override'} else {'not-run'}) -or
            $value.unknown_grammar_rule -cne $(if ($written) {'rejected-404'} else {'not-run'}) -or
            $value.grammar_written -cne $(if ($written) {'four-with-local-override'} else {'not-run'}) -or
            $value.grammar_snapshot -cne $(if ($verified) {'one-scoped-choice-four'} else {'not-run'}) -or
            $value.grammar_restarted -cne $(if ($resumed) {'four-with-local-override'} else {'not-run'}) -or
            $value.grammar_override_rows -ne [int]$verified) { throw 'Authored grammar verification order differs.' }
    }
    if ($Phase -eq 'released') {
        $script:walFiles=$value.wal_files; $script:shmFiles=$value.shm_files
        if ($walCase) {
            $script:sqliteVersion=$value.sqlite_version
            $script:transcriptWalBytes=$value.transcript_wal_bytes; $script:transcriptShmBytes=$value.transcript_shm_bytes
        }
        if ($grammarCase) { $script:grammarRows=$value.grammar_override_rows; $script:grammarVerified=$true }
    }
}
function Write-DataCopyReceipt([string]$Status) {
    $receipt=[ordered]@{schema='proxy-r19-frozen-data-copy-receipt-v1';status=$Status;source_commit=$proof.source_commit;
        build_id=$proof.build_id;case='authored-data-copy';scope='authored-transcript-copy-with-living-coordinator';
        legacy_source_sha256=(Get-FileHash -LiteralPath $slotSourceOperation -Algorithm SHA256).Hash.ToLowerInvariant();
        legacy_source_operation='existing-enter-operation';source_operation_blocked_observations=$sourceBlocks;
        authority='retained-creation-objects-and-typed-barrier';writer_console_mode='detached-process';
        api_external_side_effects='mocked';sqlite='real';database_schema_pins=@(0,0,0);authored_transcript_rows=2;
        source_cohorts=$(if ($Status -eq 'passed') {2} else {0});
        retained_writer_signals=$(if ($Status -eq 'passed') {4} else {0});
        copy_verification=$(if ($Status -eq 'passed') {'passed'} else {'not-approved'});
        source_bytes=$(if ($Status -eq 'passed') {'preserved-before-resume'} else {'not-approved'});
        source_logical=$(if ($Status -eq 'passed') {'passed-after-fresh-source-cohort'} else {'not-approved'});
        pointer=$(if ($Status -eq 'passed') {'baseline-unchanged'} else {'not-approved'});
        old_barrier=$(if ($Status -eq 'passed') {'refused-after-new-generation'} else {'not-approved'});
        wal_files=$walFiles;shm_files=$shmFiles;strict_writer_runtime_budget_ms=30000;http_transport_timeout_ms=35000;
        cleanup=$(if ($Status -eq 'passed') {'retained-writers-signaled-leases-released-private-tree-removed'} else {'unconfirmed-recovery-required'});
        failure_stage=$(if ($Status -eq 'passed') {'none'} else {$stage});
        failure_category=$(if ($Status -eq 'passed') {'none'} else {$failureCategory});
        keeper_loss='unavailable';dynamic_writer_admission='unavailable';warm_routing='unavailable';
        credentials='not-accessed';browser='not-run';target_activation=$false;production_activation=$false;
        installer='not-built';r19_complete=$false}
    if ($script:ProbeCase -ceq 'authored-data-copy-resume') {
        if ($Status -ceq 'passed' -and $sourceBlocks -ne 10) { throw 'Authored copy-resume source exclusion is incomplete.' }
        $receipt.schema='proxy-r19-frozen-data-copy-resume-receipt-v1'
        $receipt.case='authored-data-copy-resume'
        $receipt.scope='authored-transcript-interrupted-copy-resume-with-living-coordinator'
        $receipt['fault_model']='one-authored-post-file-checkpoint-exception'
        $receipt['copy_attempts']=$(if ($Status -ceq 'passed') {2} else {0})
        $receipt['authored_interruptions']=$(if ($Status -ceq 'passed') {1} else {0})
        $receipt['partial_completed_files']=$(if ($Status -ceq 'passed') {1} else {0})
        $receipt['partial_revalidations']=$(if ($Status -ceq 'passed') {2} else {0})
        $receipt['resume_authority']=$(if ($Status -ceq 'passed') {'same-live-owner-plan-barrier-generation-leases'} else {'not-approved'})
    }
    if ($script:ProbeCase -ceq 'authored-data-copy-wal') {
        if ($Status -ceq 'passed') {
            foreach ($count in @($sourceBlocks,$walFiles,$shmFiles,$transcriptWalBytes,$transcriptShmBytes)) {
                if ($count -isnot [int] -and $count -isnot [long]) { throw 'Authored WAL receipt integer differs.' }
            }
        }
        if ($Status -ceq 'passed' -and ($sourceBlocks -ne 10 -or $walFiles -lt 1 -or $shmFiles -lt 1 -or
            $walFiles -gt 3 -or $shmFiles -gt 3 -or
            $transcriptWalBytes -le 32 -or $transcriptWalBytes -gt 8388608 -or
            $transcriptShmBytes -le 0 -or $transcriptShmBytes -gt 8388608 -or
            $sqliteVersion -isnot [string] -or $sqliteVersion -cnotmatch '\A[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}\z')) {
            throw 'Authored WAL receipt proof is incomplete.'
        }
        $receipt.schema='proxy-r19-frozen-data-copy-wal-receipt-v1'
        $receipt.case='authored-data-copy-wal'
        $receipt.scope='authored-transcript-retained-wal-copy-with-living-coordinator'
        $receipt['copy_model']='one-plain-copy-without-injected-interruption'
        $receipt['sqlite_policy']='no-checkpoint-on-close-per-open-readback'
        $receipt['sqlite_version']=$sqliteVersion
        $receipt['sqlite_version_scope']='frozen-coordinator'
        $receipt['transcript_wal_bytes']=$transcriptWalBytes; $receipt['transcript_shm_bytes']=$transcriptShmBytes
        $receipt['wal_set']=$(if ($Status -ceq 'passed') {'nonempty-after-retained-signals'} else {'not-approved'})
        $receipt['wal_dependency']=$(if ($Status -ceq 'passed') {'main-only-false-full-set-true'} else {'not-approved'})
    }
    if ($script:ProbeCase -ceq 'authored-data-copy-grammar') {
        if ($Status -ceq 'passed' -and (($sourceBlocks -isnot [int] -and $sourceBlocks -isnot [long]) -or
            $sourceBlocks -ne 10 -or ($grammarRows -isnot [int] -and $grammarRows -isnot [long]) -or
            $grammarRows -ne 1 -or $grammarVerified -isnot [bool] -or -not $grammarVerified)) {
            throw 'Authored grammar receipt proof is incomplete.'
        }
        $receipt.schema='proxy-r19-frozen-data-copy-grammar-receipt-v1'
        $receipt.case='authored-data-copy-grammar'
        $receipt.scope='authored-populated-local-grammar-copy-with-living-coordinator'
        $receipt['reading_transport']='fixed-mock-settings-analysis-only'
        $receipt['grammar_credential_fixture']='in-memory-noncredential'
        $receipt['grammar_baseline']=$(if ($Status -ceq 'passed') {'zero-without-local-override'} else {'not-approved'})
        $receipt['unknown_grammar_rule']=$(if ($Status -ceq 'passed') {'rejected-404'} else {'not-approved'})
        $receipt['grammar_written']=$(if ($Status -ceq 'passed') {'four-with-local-override'} else {'not-approved'})
        $receipt['grammar_snapshot']=$(if ($Status -ceq 'passed') {'one-scoped-choice-four'} else {'not-approved'})
        $receipt['grammar_restarted']=$(if ($Status -ceq 'passed') {'four-with-local-override'} else {'not-approved'})
        $receipt['grammar_override_rows']=$(if ($Status -ceq 'passed') {$grammarRows} else {0})
    }
    New-Item -ItemType Directory -Path (Split-Path $Output) -Force | Out-Null
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Output -Encoding utf8NoBOM
}
function Wait-DataCopyRecovery {
    try { [Console]::Error.WriteLine('Authored data-copy recovery required; keep the live owner and its exclusion. External termination is failed, unverified containment.') } catch {}
    while ($true) { Start-Sleep -Seconds 5 }
}
function Complete-DataCopyHarness([bool]$Failed) {
    try { Write-DataCopyReceipt $(if ($Failed) {'failed'} else {'passed'}) }
    catch { $Failed=$true; try { Remove-Item -LiteralPath $Output -Force -ErrorAction Stop } catch {} }
    if ($Failed) {
        if (-not $script:ownerExitConfirmed) {
            $live=@($owned | Where-Object { try { $exited=$_.HasExited; ($exited -isnot [bool]) -or -not $exited } catch { $true } })
            if ($live.Count) { Wait-DataCopyRecovery }
        }
        throw 'Authored frozen data-copy probe failed; retain private evidence.'
    }
}

$RuntimeRoot=(Get-Item -LiteralPath $RuntimeRoot).FullName
$proof=Get-Content -LiteralPath $Provenance -Raw | ConvertFrom-Json
if ($proof.schema -ne 'proxy-runtime-candidate-v1' -or $proof.profile -ne 'runtime-experiment' -or
    $proof.r19_complete -ne $false -or $proof.source_commit -ne $env:GITHUB_SHA -or @($proof.files).Count -lt 1) {
    throw 'Need the exact current quarantined candidate, not an installed release.'
}
Assert-SlotInventory $RuntimeRoot $proof
$temporary=Join-Path ([IO.Path]::GetTempPath()) ('R19 data copy space 漢字 '+[guid]::NewGuid().ToString('N'))
$owned=[Collections.Generic.List[Diagnostics.Process]]::new();$controlReader=$null;$stderrDiscard=$null
$ownerExitConfirmed=$false;$sourceBlocks=0;$walFiles=0;$shmFiles=0;$stage='prepare';$failureCategory='harness-unconfirmed';$failed=$false
$sqliteVersion='';$transcriptWalBytes=0;$transcriptShmBytes=0
$grammarRows=0;$grammarVerified=$false
$roots=Get-DataCopyRoots $temporary $ProbeCase
New-Item -ItemType Directory -Path (Join-Path $temporary 'empty-host'),$roots.PROXY_TRANSCRIPT_STATE_ROOT -Force | Out-Null
@{build_id=$proof.build_id;synthetic=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $roots.PROXY_TRANSCRIPT_STATE_ROOT 'synthetic-probe.json') -Encoding utf8NoBOM
$fixture=Join-Path $roots.PROXY_TRANSCRIPT_WORK_ROOT $ProbeCase
$legacyRoot=Join-Path $fixture 'legacy'
$leasePaths=@((Join-Path $legacyRoot 'data/companion-operation.lock'),(Join-Path $fixture 'private-target/host-v1/migration-runtime.lock'))
try {
    Assert-DataCopyPortsFree
    $process=Start-DataCopyOwner
    $phases=@('setup-closed','favorite-written')
    if ($ProbeCase -ceq 'authored-data-copy-grammar') { $phases+=@('grammar-written') }
    $phases+=@('strict-drain-complete','writers-signaled')
    if ($ProbeCase -ceq 'authored-data-copy-wal') { $phases+=@('wal-set-observed') }
    $phases+=@('copy-progress')
    if ($ProbeCase -ceq 'authored-data-copy-resume') { $phases+=@('copy-interrupted') }
    $phases+=@('copy-verified','source-resumed','final-strict-drain-complete','final-writers-signaled')
    foreach ($phase in $phases) {
        $stage=$phase
        Read-DataCopyEvent $phase
        Assert-DataCopyLeases 'blocked'
        $process.StandardInput.WriteLine('observed '+$phase);$process.StandardInput.Flush()
    }
    $stage='release'
    Read-DataCopyEvent 'released'
    $process.StandardInput.Close()
    if (-not $process.WaitForExit(15000) -or $process.ExitCode -ne 0) { throw 'Retained data-copy owner did not exit successfully.' }
    $script:ownerExitConfirmed=$true
    if ($null -ne (Read-DataCopyControlLine $script:controlReader 5000 $true)) { throw 'Unexpected trailing data-copy control event.' }
    if (-not $stderrDiscard.Wait(5000)) { throw 'Authored stderr discard did not finish.' }
    $null=$stderrDiscard.GetAwaiter().GetResult()
    Assert-DataCopyLeases 'open'
    Assert-DataCopyPortsFree
    Assert-SlotInventory $RuntimeRoot $proof
    $stage='private-cleanup'
    Remove-Item -LiteralPath $temporary -Recurse -Force
    foreach ($process in $owned) { $process.Dispose() }
} catch {
    $failed=$true
    if ($null -ne $controlReader -and $controlReader.fault -cin @('control-overflow','control-eof',
        'control-invalid-utf8','control-reader-unavailable','control-deadline','stderr-unavailable')) {
        $failureCategory=$controlReader.fault
    }
}
# A passing receipt cannot precede process, lease, inventory and private cleanup.
Complete-DataCopyHarness $failed
Write-Host 'Authored transcript copy verified with living coordinator and fresh source cohort; production migration remains disabled.'
