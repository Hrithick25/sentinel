/**
 * SENTINEL — Dashboard Webview Panel
 * Opens the existing SENTINEL dashboard (deployed Vercel app) inside VS Code,
 * or shows a local summary if the dashboard URL is unavailable.
 */
import * as vscode from 'vscode';
import { SentinelClient } from '../client';

export class DashboardPanel {
    public static currentPanel: DashboardPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _client: SentinelClient;
    private _disposed = false;

    static show(extensionUri: vscode.Uri, client: SentinelClient) {
        if (DashboardPanel.currentPanel) {
            DashboardPanel.currentPanel._panel.reveal(vscode.ViewColumn.One);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'sentinelDashboard',
            '🛡️ SENTINEL Dashboard',
            vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            },
        );

        DashboardPanel.currentPanel = new DashboardPanel(panel, client);
    }

    private constructor(panel: vscode.WebviewPanel, client: SentinelClient) {
        this._panel = panel;
        this._client = client;

        this._update();

        this._panel.onDidDispose(() => {
            this._disposed = true;
            DashboardPanel.currentPanel = undefined;
        });
    }

    private async _update() {
        let healthHtml = '';
        let analyticsHtml = '';

        try {
            const health = await this._client.health();
            healthHtml = `
                <div class="card success">
                    <h3>🟢 Gateway Online</h3>
                    <div class="stats-grid">
                        <div class="stat"><span class="stat-value">${health.version}</span><span class="stat-label">Version</span></div>
                        <div class="stat"><span class="stat-value">${health.agents}</span><span class="stat-label">Agents</span></div>
                        <div class="stat"><span class="stat-value">${health.faiss_vectors}</span><span class="stat-label">FAISS Vectors</span></div>
                        <div class="stat"><span class="stat-value">${Math.floor(health.uptime_seconds / 60)}m</span><span class="stat-label">Uptime</span></div>
                    </div>
                </div>
            `;
        } catch {
            healthHtml = `<div class="card error"><h3>🔴 Gateway Offline</h3><p>Configure gateway URL in VS Code Settings → SENTINEL</p></div>`;
        }

        try {
            const analytics = await this._client.analytics();
            analyticsHtml = `
                <div class="card">
                    <h3>📊 Last 24h Analytics</h3>
                    <div class="stats-grid">
                        <div class="stat"><span class="stat-value">${analytics.total_requests || 0}</span><span class="stat-label">Total Requests</span></div>
                        <div class="stat"><span class="stat-value blocked">${analytics.blocked || 0}</span><span class="stat-label">Blocked</span></div>
                        <div class="stat"><span class="stat-value warn">${analytics.rewritten || 0}</span><span class="stat-label">Rewritten</span></div>
                        <div class="stat"><span class="stat-value safe">${analytics.allowed || 0}</span><span class="stat-label">Allowed</span></div>
                        <div class="stat"><span class="stat-value">${(analytics.avg_latency_ms || 0).toFixed(1)}ms</span><span class="stat-label">Avg Latency</span></div>
                        <div class="stat"><span class="stat-value">${((analytics.detection_rate || 0) * 100).toFixed(1)}%</span><span class="stat-label">Detection Rate</span></div>
                    </div>
                </div>
            `;
        } catch {
            analyticsHtml = `<div class="card muted"><h3>📊 Analytics</h3><p>Connect to gateway to view analytics</p></div>`;
        }

        this._panel.webview.html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SENTINEL Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
            padding: 24px;
        }
        .header {
            display: flex; align-items: center; gap: 16px;
            margin-bottom: 32px; padding-bottom: 16px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .header h1 { font-size: 24px; font-weight: 700; }
        .header .badge {
            background: rgba(34, 197, 94, 0.15); color: #22c55e;
            padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;
        }
        .card {
            background: var(--vscode-editorWidget-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 8px; padding: 20px; margin-bottom: 16px;
        }
        .card.success { border-left: 4px solid #22c55e; }
        .card.error { border-left: 4px solid #ef4444; }
        .card.muted { opacity: 0.6; }
        .card h3 { margin-bottom: 16px; font-size: 16px; }
        .stats-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 16px;
        }
        .stat { text-align: center; }
        .stat-value { display: block; font-size: 24px; font-weight: 700; margin-bottom: 4px; }
        .stat-value.blocked { color: #ef4444; }
        .stat-value.warn { color: #f59e0b; }
        .stat-value.safe { color: #22c55e; }
        .stat-label { font-size: 12px; opacity: 0.6; text-transform: uppercase; letter-spacing: 0.5px; }
        .agents-section { margin-top: 24px; }
        .agents-section h3 { margin-bottom: 12px; }
        .agent-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 8px;
        }
        .agent-chip {
            background: var(--vscode-badge-background); color: var(--vscode-badge-foreground);
            padding: 6px 12px; border-radius: 6px; font-size: 12px; font-family: monospace;
        }
        .footer {
            margin-top: 32px; padding-top: 16px;
            border-top: 1px solid var(--vscode-panel-border);
            font-size: 12px; opacity: 0.5;
        }
        a { color: var(--vscode-textLink-foreground); text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ SENTINEL</h1>
        <span class="badge">v5.0 Enterprise</span>
        <span class="badge">19-Agent Mesh</span>
    </div>

    ${healthHtml}
    ${analyticsHtml}

    <div class="agents-section">
        <div class="card">
            <h3>🧬 19-Agent Security Mesh</h3>
            <div class="agent-grid">
                <div class="agent-chip">🔍 InjectionScout</div>
                <div class="agent-chip">🔒 PIISentinel</div>
                <div class="agent-chip">🚫 JailbreakGuard</div>
                <div class="agent-chip">☠️ ToxicityScreener</div>
                <div class="agent-chip">🎭 HallucinationProbe</div>
                <div class="agent-chip">⚓ ContextAnchor</div>
                <div class="agent-chip">📋 ComplianceTagger</div>
                <div class="agent-chip">🛡️ ResponseSafety</div>
                <div class="agent-chip">🌐 MultilingualGuard</div>
                <div class="agent-chip">🗺️ LocaleRouter</div>
                <div class="agent-chip">🔧 ToolCallSafety</div>
                <div class="agent-chip">™️ BrandGuard</div>
                <div class="agent-chip">📊 TokenAnomaly</div>
                <div class="agent-chip">🧬 PromptLineage</div>
                <div class="agent-chip">🧠 IntentClassifier</div>
                <div class="agent-chip">🔄 AdversarialRephrase</div>
                <div class="agent-chip">⚡ JailbreakPattern</div>
                <div class="agent-chip">💰 CostAnomaly</div>
                <div class="agent-chip">🔁 AgenticLoopBreaker</div>
            </div>
        </div>
    </div>

    <div class="footer">
        SENTINEL LLM Trust & Safety Infrastructure · 
        <a href="https://github.com/Hrithick25/sentinel">GitHub</a> · 
        <a href="https://sentinel-ai.dev">sentinel-ai.dev</a>
    </div>
</body>
</html>`;
    }
}
