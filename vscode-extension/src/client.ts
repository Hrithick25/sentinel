/**
 * SENTINEL HTTP Client for VS Code Extension
 * =============================================
 * Lightweight HTTP client that communicates with the SENTINEL Gateway.
 * Uses VS Code's built-in https module (zero external dependencies).
 */

import * as http from 'http';
import * as https from 'https';
import { URL } from 'url';

export interface ClientConfig {
    gatewayUrl: string;
    tenantId: string;
    apiKey: string;
}

export interface ScreenResult {
    request_id: string;
    decision: string;
    aggregate_score: number;
    ml_risk_score: number;
    agent_scores: Record<string, number>;
    triggering_agent: string | null;
    latency_ms: number;
}

export interface TrustResult {
    trust_score: number;
    threat_score: number;
    ml_risk_score: number;
    consensus_score: number;
    flagged_agents: Array<{ agent: string; score: number }>;
    veto_agents: string[];
    latency_ms: number;
}

export interface HealthResult {
    status: string;
    version: string;
    agents: number;
    faiss_vectors: number;
    uptime_seconds: number;
    v5_agents: string[];
}

export class SentinelClient {
    private gatewayUrl: string;
    private tenantId: string;
    private apiKey: string;

    constructor(config: ClientConfig) {
        this.gatewayUrl = config.gatewayUrl.replace(/\/+$/, '');
        this.tenantId = config.tenantId;
        this.apiKey = config.apiKey;
    }

    private async request<T>(method: string, path: string, body?: any): Promise<T> {
        return new Promise((resolve, reject) => {
            const url = new URL(path, this.gatewayUrl);
            const isHttps = url.protocol === 'https:';
            const transport = isHttps ? https : http;

            const headers: Record<string, string> = {
                'Content-Type': 'application/json',
                'User-Agent': 'SENTINEL-VSCode/1.0',
            };

            if (this.apiKey) {
                headers['Authorization'] = `Bearer ${this.apiKey}`;
            }

            const payload = body ? JSON.stringify(body) : undefined;
            if (payload) {
                headers['Content-Length'] = Buffer.byteLength(payload).toString();
            }

            const req = transport.request({
                hostname: url.hostname,
                port: url.port || (isHttps ? 443 : 80),
                path: url.pathname + url.search,
                method,
                headers,
                timeout: 15000,
            }, (res) => {
                let data = '';
                res.on('data', (chunk: string) => { data += chunk; });
                res.on('end', () => {
                    try {
                        if (res.statusCode && res.statusCode >= 400) {
                            reject(new Error(`HTTP ${res.statusCode}: ${data.substring(0, 200)}`));
                            return;
                        }
                        resolve(JSON.parse(data) as T);
                    } catch (e) {
                        reject(new Error(`Invalid JSON response: ${data.substring(0, 100)}`));
                    }
                });
            });

            req.on('error', (err) => reject(new Error(`Connection failed: ${err.message}`)));
            req.on('timeout', () => {
                req.destroy();
                reject(new Error('Request timed out after 15s'));
            });

            if (payload) {
                req.write(payload);
            }
            req.end();
        });
    }

    async screen(text: string): Promise<ScreenResult> {
        return this.request<ScreenResult>('POST', '/v1/screen', {
            tenant_id: this.tenantId || 'vscode-user',
            messages: [{ role: 'user', content: text }],
        });
    }

    async trustScore(text: string): Promise<TrustResult> {
        return this.request<TrustResult>('POST', '/v1/trust-score', {
            tenant_id: this.tenantId || 'vscode-user',
            messages: [{ role: 'user', content: text }],
        });
    }

    async health(): Promise<HealthResult> {
        return this.request<HealthResult>('GET', '/health');
    }

    async analytics(): Promise<any> {
        return this.request<any>('GET', '/v1/analytics');
    }
}
