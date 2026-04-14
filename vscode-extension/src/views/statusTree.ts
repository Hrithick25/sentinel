/**
 * SENTINEL — Gateway Status Tree View
 */
import * as vscode from 'vscode';
import { SentinelClient } from '../client';

export class StatusTreeProvider implements vscode.TreeDataProvider<StatusItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<StatusItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private client: SentinelClient;
    private healthData: any = null;

    constructor(client: SentinelClient) {
        this.client = client;
    }

    updateClient(client: SentinelClient) {
        this.client = client;
        this.refresh();
    }

    refresh() {
        this.client.health().then(data => {
            this.healthData = data;
            this._onDidChangeTreeData.fire(undefined);
        }).catch(() => {
            this.healthData = null;
            this._onDidChangeTreeData.fire(undefined);
        });
    }

    getTreeItem(element: StatusItem): vscode.TreeItem {
        return element;
    }

    getChildren(): StatusItem[] {
        if (!this.healthData) {
            return [
                new StatusItem('Status', '❌ Disconnected', vscode.TreeItemCollapsibleState.None),
                new StatusItem('Action', 'Configure gateway URL in Settings', vscode.TreeItemCollapsibleState.None),
            ];
        }

        const h = this.healthData;
        return [
            new StatusItem('Status', `✅ Connected (v${h.version})`, vscode.TreeItemCollapsibleState.None),
            new StatusItem('Agents', `${h.agents} active`, vscode.TreeItemCollapsibleState.None),
            new StatusItem('FAISS Vectors', `${h.faiss_vectors} attack signatures`, vscode.TreeItemCollapsibleState.None),
            new StatusItem('Uptime', `${Math.floor(h.uptime_seconds / 60)}m ${h.uptime_seconds % 60}s`, vscode.TreeItemCollapsibleState.None),
            new StatusItem('v5 Agents', h.v5_agents?.join(', ') || 'N/A', vscode.TreeItemCollapsibleState.None),
        ];
    }
}

class StatusItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        private value: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
    ) {
        super(label, collapsibleState);
        this.description = value;
        this.tooltip = `${label}: ${value}`;
    }
}
