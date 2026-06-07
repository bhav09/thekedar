import * as vscode from 'vscode';

export interface IdeTask {
    id: string;
    tenant_id: string;
    run_id: string;
    status: string;
    payload_json: string;
    created_at: string;
}

export class ThekedarApiClient {
    private get baseUrl(): string {
        const config = vscode.workspace.getConfiguration('thekedar');
        return config.get<string>('dashboardUrl', 'http://localhost:8081');
    }

    private get token(): string {
        const config = vscode.workspace.getConfiguration('thekedar');
        return config.get<string>('token', '');
    }

    private get headers(): Record<string, string> {
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.token}`,
        };
    }

    async getPendingTasks(): Promise<IdeTask[]> {
        if (!this.token) {
            return [];
        }
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/ide-tasks/pending`, {
                method: 'GET',
                headers: this.headers,
            });
            if (response.ok) {
                return (await response.json()) as IdeTask[];
            }
            return [];
        } catch (e) {
            console.error('Thekedar getPendingTasks failed:', e);
            return [];
        }
    }

    async claimTask(taskId: string, claimedBy: string): Promise<boolean> {
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/ide-tasks/${taskId}/claim`, {
                method: 'POST',
                headers: this.headers,
                body: JSON.stringify({ claimed_by: claimedBy }),
            });
            return response.ok;
        } catch (e) {
            console.error(`Thekedar claimTask ${taskId} failed:`, e);
            return false;
        }
    }

    async completeTask(taskId: string, resultJson: string): Promise<boolean> {
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/ide-tasks/${taskId}/complete`, {
                method: 'POST',
                headers: this.headers,
                body: JSON.stringify({ result_json: resultJson }),
            });
            return response.ok;
        } catch (e) {
            console.error(`Thekedar completeTask ${taskId} failed:`, e);
            return false;
        }
    }

    async failTask(taskId: string, error: string): Promise<boolean> {
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/ide-tasks/${taskId}/fail`, {
                method: 'POST',
                headers: this.headers,
                body: JSON.stringify({ error }),
            });
            return response.ok;
        } catch (e) {
            console.error(`Thekedar failTask ${taskId} failed:`, e);
            return false;
        }
    }
}
