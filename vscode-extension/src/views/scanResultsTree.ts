/**
 * SENTINEL — Scan Results Tree View
 */
import * as vscode from 'vscode';

export interface ScanResultItem {
    text: string;
    decision: string;
    score: number;
    trigger: string;
    latency: number;
    timestamp: Date;
}

export class ScanResultsProvider implements vscode.TreeDataProvider<ScanTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<ScanTreeItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private results: ScanResultItem[] = [];

    addResult(item: ScanResultItem) {
        this.results.unshift(item);
        if (this.results.length > 50) {
            this.results = this.results.slice(0, 50);
        }
        this._onDidChangeTreeData.fire(undefined);
    }

    clear() {
        this.results = [];
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: ScanTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(): ScanTreeItem[] {
        if (this.results.length === 0) {
            return [new ScanTreeItem('No scans yet', 'Select text → Right click → Screen with SENTINEL', 'info')];
        }

        return this.results.map(r => {
            const icon = r.decision === 'BLOCK' ? '🔴' : r.decision === 'REWRITE' ? '🟡' : '🟢';
            const label = `${icon} ${r.decision}`;
            const desc = `${(r.score * 100).toFixed(1)}% | ${r.latency.toFixed(0)}ms | ${r.text.substring(0, 40)}...`;
            return new ScanTreeItem(label, desc, r.decision.toLowerCase());
        });
    }
}

class ScanTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        private desc: string,
        private type: string,
    ) {
        super(label, vscode.TreeItemCollapsibleState.None);
        this.description = desc;
        this.tooltip = desc;

        if (type === 'block') {
            this.iconPath = new vscode.ThemeIcon('error', new vscode.ThemeColor('errorForeground'));
        } else if (type === 'rewrite') {
            this.iconPath = new vscode.ThemeIcon('warning', new vscode.ThemeColor('editorWarning.foreground'));
        } else if (type === 'allow') {
            this.iconPath = new vscode.ThemeIcon('pass', new vscode.ThemeColor('testing.iconPassed'));
        }
    }
}
