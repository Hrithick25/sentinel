/**
 * SENTINEL — Agent Mesh Tree View
 * Shows all 19 agents organized by version tier.
 */
import * as vscode from 'vscode';

interface AgentInfo {
    name: string;
    description: string;
    tier: string;
}

const AGENTS: AgentInfo[] = [
    // v1
    { name: 'InjectionScout', description: 'FAISS ANN + regex prompt injection detection', tier: 'v1' },
    { name: 'PIISentinel', description: 'SpaCy NER + regex PII detection (GDPR/HIPAA)', tier: 'v1' },
    { name: 'JailbreakGuard', description: 'Classic jailbreak pattern matching', tier: 'v1' },
    { name: 'ToxicityScreener', description: 'Detoxify 6-dim toxicity scoring', tier: 'v1' },
    { name: 'HallucinationProbe', description: 'NLI-based claim extraction + grounding check', tier: 'v1' },
    { name: 'ContextAnchor', description: 'Source context fidelity verification', tier: 'v1' },
    { name: 'ComplianceTagger', description: 'HIPAA/GDPR/SOC2/DPDP compliance tagging', tier: 'v1' },
    // v2
    { name: 'ResponseSafetyLayer', description: 'Universal model output validation', tier: 'v2' },
    { name: 'MultilingualGuard', description: 'Cross-language attack detection', tier: 'v2' },
    { name: 'LocaleComplianceRouter', description: 'Region-aware compliance routing', tier: 'v2' },
    { name: 'ToolCallSafety', description: 'SSRF/path-traversal tool-call validation', tier: 'v2' },
    { name: 'BrandGuard', description: 'Brand mention & competitor detection', tier: 'v2' },
    { name: 'TokenAnomalyDetector', description: 'Token usage pattern anomaly detection', tier: 'v2' },
    // v3
    { name: 'PromptLineage', description: 'Prompt history tracking & mutation detection', tier: 'v3' },
    { name: 'IntentClassifier', description: 'Multi-label intent classification (13 labels)', tier: 'v3' },
    { name: 'AdversarialRephrasing', description: 'Semantic-preserving rephrase detection', tier: 'v3' },
    // v4
    { name: 'JailbreakPatternDetector', description: '65+ signatures, DAN, crescendo attacks', tier: 'v4' },
    { name: 'CostAnomalyDetector', description: 'Runaway token cost & inference bomb detection', tier: 'v4' },
    { name: 'AgenticLoopBreaker', description: 'Infinite tool-call loop detection', tier: 'v4' },
];

export class AgentTreeProvider implements vscode.TreeDataProvider<AgentTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<AgentTreeItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    refresh() {
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: AgentTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: AgentTreeItem): AgentTreeItem[] {
        if (!element) {
            // Root level: tier groups
            const tiers = ['v1', 'v2', 'v3', 'v4'];
            const tierLabels: Record<string, string> = {
                'v1': '🛡️ Core Agents (7)',
                'v2': '🔒 Enterprise Agents (6)',
                'v3': '🧠 Intelligence Agents (3)',
                'v4': '⚡ Advanced Agents (3)',
            };
            return tiers.map(t => new AgentTreeItem(
                tierLabels[t] || t,
                '',
                vscode.TreeItemCollapsibleState.Expanded,
                t,
            ));
        }

        // Children: agents in this tier
        return AGENTS
            .filter(a => a.tier === element.tier)
            .map(a => new AgentTreeItem(
                a.name,
                a.description,
                vscode.TreeItemCollapsibleState.None,
            ));
    }
}

class AgentTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        private desc: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly tier?: string,
    ) {
        super(label, collapsibleState);
        this.description = desc;
        this.tooltip = desc ? `${label}: ${desc}` : label;

        if (!tier) {
            this.iconPath = new vscode.ThemeIcon('symbol-method');
        }
    }
}
