import * as vscode from 'vscode';
import { ThekedarTaskRunner } from './taskRunner';
import { registerSidebar } from './webview/sidebar';

let taskRunner: ThekedarTaskRunner | null = null;

export function activate(context: vscode.ExtensionContext) {
    console.log('Thekedar Extension activated successfully.');

    // 1. Register the Sidebar View
    registerSidebar(context);

    // 2. Initialize and start the bidirectional Task Runner
    taskRunner = new ThekedarTaskRunner();
    taskRunner.start();

    // 3. Register user commands
    const openDashboardCommand = vscode.commands.registerCommand('thekedar.openDashboard', () => {
        const config = vscode.workspace.getConfiguration('thekedar');
        const url = config.get<string>('dashboardUrl', 'http://localhost:8081');
        vscode.env.openExternal(vscode.Uri.parse(url));
    });

    const triggerDoctorCommand = vscode.commands.registerCommand('thekedar.triggerDoctor', () => {
        const terminal = vscode.window.createTerminal('Thekedar Doctor');
        terminal.show();
        terminal.sendText('uv run python -m thekedar_cli doctor');
    });

    context.subscriptions.push(openDashboardCommand);
    context.subscriptions.push(triggerDoctorCommand);
}

export function deactivate() {
    if (taskRunner) {
        taskRunner.stop();
        taskRunner = null;
    }
}
