/**
 * SENTINEL — VS Code Extension Entry Point
 * ==========================================
 * Integrates the SENTINEL LLM Trust & Safety Gateway directly into VS Code.
 * 
 * Features:
 *   - Screen selected text for prompt injection / PII / jailbreak / toxicity
 *   - Get 0-100 trust scores for any text
 *   - Sidebar with gateway status, scan results, and agent mesh overview
 *   - Inline decorations showing threat scores
 *   - Auto-scan on save (optional)
 *   - Full dashboard webview panel
 */

import * as vscode from 'vscode';
import { SentinelClient } from './client';
import { StatusTreeProvider } from './views/statusTree';
import { ScanResultsProvider, ScanResultItem } from './views/scanResultsTree';
import { AgentTreeProvider } from './views/agentTree';
import { DashboardPanel } from './views/dashboardPanel';

let client: SentinelClient;
let statusBar: vscode.StatusBarItem;
let outputChannel: vscode.OutputChannel;
let statusProvider: StatusTreeProvider;
let scanProvider: ScanResultsProvider;
let agentProvider: AgentTreeProvider;

// Decoration types for inline threat highlighting
const dangerDecoration = vscode.window.createTextEditorDecorationType({
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    border: '1px solid rgba(239, 68, 68, 0.5)',
    borderRadius: '3px',
    after: {
        margin: '0 0 0 8px',
        color: 'rgba(239, 68, 68, 0.8)',
        fontWeight: 'bold',
        fontStyle: 'italic',
    },
});

const warnDecoration = vscode.window.createTextEditorDecorationType({
    backgroundColor: 'rgba(245, 158, 11, 0.12)',
    border: '1px solid rgba(245, 158, 11, 0.4)',
    borderRadius: '3px',
    after: {
        margin: '0 0 0 8px',
        color: 'rgba(245, 158, 11, 0.7)',
        fontStyle: 'italic',
    },
});

const safeDecoration = vscode.window.createTextEditorDecorationType({
    after: {
        margin: '0 0 0 8px',
        color: 'rgba(34, 197, 94, 0.6)',
        fontStyle: 'italic',
    },
});

export function activate(context: vscode.ExtensionContext) {
    outputChannel = vscode.window.createOutputChannel('SENTINEL');
    outputChannel.appendLine('🛡️  SENTINEL extension activated');

    // Initialize client from settings
    client = createClientFromConfig();

    // Status bar
    statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBar.command = 'sentinel.healthCheck';
    statusBar.text = '$(shield) SENTINEL';
    statusBar.tooltip = 'SENTINEL LLM Security — Click for health check';
    statusBar.show();

    // Tree view providers
    statusProvider = new StatusTreeProvider(client);
    scanProvider = new ScanResultsProvider();
    agentProvider = new AgentTreeProvider();

    vscode.window.registerTreeDataProvider('sentinel.status', statusProvider);
    vscode.window.registerTreeDataProvider('sentinel.scanResults', scanProvider);
    vscode.window.registerTreeDataProvider('sentinel.agents', agentProvider);

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('sentinel.screenSelection', screenSelection),
        vscode.commands.registerCommand('sentinel.trustScore', getTrustScore),
        vscode.commands.registerCommand('sentinel.screenFile', screenFile),
        vscode.commands.registerCommand('sentinel.showDashboard', () => DashboardPanel.show(context.extensionUri, client)),
        vscode.commands.registerCommand('sentinel.healthCheck', healthCheck),
        statusBar,
        outputChannel,
    );

    // Listen for config changes
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration(e => {
            if (e.affectsConfiguration('sentinel')) {
                client = createClientFromConfig();
                statusProvider.updateClient(client);
                outputChannel.appendLine('⚙️  Configuration updated');
            }
        })
    );

    // Auto-scan on save (if enabled)
    context.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument(doc => {
            const config = vscode.workspace.getConfiguration('sentinel');
            if (config.get<boolean>('autoScan')) {
                autoScanDocument(doc);
            }
        })
    );

    // Initial health check
    healthCheck(true);
}

function createClientFromConfig(): SentinelClient {
    const config = vscode.workspace.getConfiguration('sentinel');
    return new SentinelClient({
        gatewayUrl: config.get<string>('gatewayUrl') || 'http://localhost:8000',
        tenantId: config.get<string>('tenantId') || '',
        apiKey: config.get<string>('apiKey') || '',
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
//  COMMANDS
// ═══════════════════════════════════════════════════════════════════════════════

async function screenSelection() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    const selection = editor.selection;
    const text = editor.document.getText(selection);
    if (!text.trim()) {
        vscode.window.showWarningMessage('No text selected');
        return;
    }

    statusBar.text = '$(loading~spin) Scanning...';
    outputChannel.appendLine(`\n━━━ Screening text (${text.length} chars) ━━━`);

    try {
        const result = await client.screen(text);
        outputChannel.appendLine(`Decision:    ${result.decision}`);
        outputChannel.appendLine(`Score:       ${result.aggregate_score.toFixed(4)}`);
        outputChannel.appendLine(`ML Risk:     ${result.ml_risk_score.toFixed(4)}`);
        outputChannel.appendLine(`Trigger:     ${result.triggering_agent || 'none'}`);
        outputChannel.appendLine(`Latency:     ${result.latency_ms.toFixed(1)}ms`);
        outputChannel.appendLine(`Agent Scores:`);
        for (const [agent, score] of Object.entries(result.agent_scores)) {
            const bar = '█'.repeat(Math.round(Number(score) * 20));
            outputChannel.appendLine(`  ${agent.padEnd(28)} ${Number(score).toFixed(4)} ${bar}`);
        }

        // Apply decoration
        const config = vscode.workspace.getConfiguration('sentinel');
        const blockThresh = config.get<number>('blockThreshold') || 0.7;
        const warnThresh = config.get<number>('warnThreshold') || 0.35;

        if (config.get<boolean>('showInlineScores')) {
            const range = new vscode.Range(selection.start, selection.end);
            if (result.aggregate_score >= blockThresh) {
                editor.setDecorations(dangerDecoration, [{
                    range,
                    renderOptions: {
                        after: { contentText: `⛔ BLOCK ${(result.aggregate_score * 100).toFixed(0)}%` }
                    }
                }]);
            } else if (result.aggregate_score >= warnThresh) {
                editor.setDecorations(warnDecoration, [{
                    range,
                    renderOptions: {
                        after: { contentText: `⚠️ WARN ${(result.aggregate_score * 100).toFixed(0)}%` }
                    }
                }]);
            } else {
                editor.setDecorations(safeDecoration, [{
                    range,
                    renderOptions: {
                        after: { contentText: `✅ SAFE ${(result.aggregate_score * 100).toFixed(0)}%` }
                    }
                }]);
            }
        }

        // Update scan results tree
        scanProvider.addResult({
            text: text.substring(0, 80) + (text.length > 80 ? '...' : ''),
            decision: result.decision,
            score: result.aggregate_score,
            trigger: result.triggering_agent || '',
            latency: result.latency_ms,
            timestamp: new Date(),
        });

        // Show notification
        const icon = result.decision === 'BLOCK' ? '🔴' : result.decision === 'REWRITE' ? '🟡' : '🟢';
        vscode.window.showInformationMessage(
            `${icon} SENTINEL: ${result.decision} | Score: ${(result.aggregate_score * 100).toFixed(1)}% | ${result.latency_ms.toFixed(0)}ms`
        );

        statusBar.text = `$(shield) ${icon} ${result.decision}`;
        setTimeout(() => { statusBar.text = '$(shield) SENTINEL'; }, 5000);

    } catch (err: any) {
        outputChannel.appendLine(`❌ Error: ${err.message}`);
        vscode.window.showErrorMessage(`SENTINEL Error: ${err.message}`);
        statusBar.text = '$(shield) SENTINEL ❌';
    }
}

async function getTrustScore() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) { return; }

    const text = editor.document.getText(editor.selection);
    if (!text.trim()) {
        vscode.window.showWarningMessage('No text selected');
        return;
    }

    statusBar.text = '$(loading~spin) Scoring...';

    try {
        const result = await client.trustScore(text);
        const emoji = result.trust_score >= 70 ? '🟢' : result.trust_score >= 40 ? '🟡' : '🔴';

        outputChannel.appendLine(`\n━━━ Trust Score ━━━`);
        outputChannel.appendLine(`Trust:   ${result.trust_score}/100 ${emoji}`);
        outputChannel.appendLine(`Threat:  ${result.threat_score.toFixed(4)}`);
        outputChannel.appendLine(`ML Risk: ${result.ml_risk_score.toFixed(4)}`);
        if (result.flagged_agents.length > 0) {
            outputChannel.appendLine(`Flagged: ${result.flagged_agents.map((a: any) => a.agent).join(', ')}`);
        }
        if (result.veto_agents.length > 0) {
            outputChannel.appendLine(`Vetoed:  ${result.veto_agents.join(', ')}`);
        }

        vscode.window.showInformationMessage(
            `${emoji} Trust Score: ${result.trust_score}/100 | Threat: ${(result.threat_score * 100).toFixed(1)}% | ${result.latency_ms.toFixed(0)}ms`
        );

        statusBar.text = `$(shield) Trust: ${result.trust_score}`;
        setTimeout(() => { statusBar.text = '$(shield) SENTINEL'; }, 5000);

    } catch (err: any) {
        vscode.window.showErrorMessage(`SENTINEL Error: ${err.message}`);
        statusBar.text = '$(shield) SENTINEL ❌';
    }
}

async function screenFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) { return; }

    const fullText = editor.document.getText();
    // Extract string literals from code
    const stringPattern = /(?:["'`])([^"'`]{10,})(?:["'`])/g;
    let match;
    const candidates: { text: string; range: vscode.Range }[] = [];

    while ((match = stringPattern.exec(fullText)) !== null) {
        const start = editor.document.positionAt(match.index + 1);
        const end = editor.document.positionAt(match.index + 1 + match[1].length);
        candidates.push({ text: match[1], range: new vscode.Range(start, end) });
    }

    if (candidates.length === 0) {
        vscode.window.showInformationMessage('No string literals found to scan');
        return;
    }

    statusBar.text = `$(loading~spin) Scanning ${candidates.length} strings...`;
    outputChannel.appendLine(`\n━━━ File Scan: ${candidates.length} strings ━━━`);

    const config = vscode.workspace.getConfiguration('sentinel');
    const blockThresh = config.get<number>('blockThreshold') || 0.7;
    const warnThresh = config.get<number>('warnThreshold') || 0.35;

    const dangerRanges: vscode.DecorationOptions[] = [];
    const warnRanges: vscode.DecorationOptions[] = [];
    const safeRanges: vscode.DecorationOptions[] = [];
    let threats = 0;

    for (const candidate of candidates.slice(0, 20)) { // cap at 20 to avoid flooding
        try {
            const result = await client.screen(candidate.text);
            if (result.aggregate_score >= blockThresh) {
                threats++;
                dangerRanges.push({
                    range: candidate.range,
                    renderOptions: {
                        after: { contentText: ` ⛔ ${(result.aggregate_score * 100).toFixed(0)}%` }
                    }
                });
            } else if (result.aggregate_score >= warnThresh) {
                warnRanges.push({
                    range: candidate.range,
                    renderOptions: {
                        after: { contentText: ` ⚠️ ${(result.aggregate_score * 100).toFixed(0)}%` }
                    }
                });
            } else {
                safeRanges.push({
                    range: candidate.range,
                    renderOptions: {
                        after: { contentText: ` ✅` }
                    }
                });
            }
        } catch {
            // skip on error
        }
    }

    editor.setDecorations(dangerDecoration, dangerRanges);
    editor.setDecorations(warnDecoration, warnRanges);
    editor.setDecorations(safeDecoration, safeRanges);

    const msg = threats > 0
        ? `🔴 ${threats} threat(s) found in ${candidates.length} strings`
        : `🟢 All ${candidates.length} strings passed SENTINEL scan`;
    vscode.window.showInformationMessage(msg);
    statusBar.text = '$(shield) SENTINEL';
}

async function healthCheck(silent: boolean = false) {
    try {
        const health = await client.health();
        statusBar.text = `$(shield) SENTINEL v${health.version} ✅`;
        statusBar.tooltip = `SENTINEL Gateway: ${health.agents} agents | ${health.faiss_vectors} FAISS vectors | Uptime: ${health.uptime_seconds}s`;
        statusProvider.refresh();
        agentProvider.refresh();

        if (!silent) {
            vscode.window.showInformationMessage(
                `🛡️ SENTINEL Gateway v${health.version} — ${health.agents} agents active, ${health.faiss_vectors} attack vectors indexed`
            );
        }
        outputChannel.appendLine(`✅ Gateway health: ${JSON.stringify(health)}`);
    } catch (err: any) {
        statusBar.text = '$(shield) SENTINEL ❌';
        statusBar.tooltip = `SENTINEL Gateway unreachable: ${err.message}`;
        if (!silent) {
            vscode.window.showErrorMessage(
                `SENTINEL Gateway unreachable: ${err.message}. Configure via Settings → SENTINEL → Gateway URL`
            );
        }
        outputChannel.appendLine(`❌ Health check failed: ${err.message}`);
    }
}

async function autoScanDocument(doc: vscode.TextDocument) {
    const editor = vscode.window.visibleTextEditors.find(e => e.document === doc);
    if (!editor) { return; }

    // Only scan Python/JS/TS files with prompt-like strings
    const langIds = ['python', 'javascript', 'typescript', 'javascriptreact', 'typescriptreact'];
    if (!langIds.includes(doc.languageId)) { return; }

    outputChannel.appendLine(`🔄 Auto-scanning ${doc.fileName}`);
    await screenFile();
}

export function deactivate() {
    outputChannel?.appendLine('🔴 SENTINEL extension deactivated');
}
