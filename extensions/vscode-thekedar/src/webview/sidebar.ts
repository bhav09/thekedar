import * as vscode from 'vscode';

export class ThekedarSidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'thekedar-sidebar';
    private _view?: vscode.WebviewView;

    resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        const config = vscode.workspace.getConfiguration('thekedar');
        const dashboardUrl = config.get<string>('dashboardUrl', 'http://localhost:8081');

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thekedar Actions</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            color: var(--vscode-foreground);
            padding: 15px;
        }
        .btn {
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 8px 12px;
            width: 100%;
            cursor: pointer;
            margin-bottom: 10px;
            text-align: center;
            font-weight: bold;
        }
        .btn:hover {
            background-color: var(--vscode-button-hoverBackground);
        }
        .card {
            background-color: var(--vscode-welcomePage-tileBackground);
            border: 1px solid var(--vscode-welcomePage-border);
            padding: 10px;
            margin-bottom: 15px;
            font-size: 12px;
        }
        h3 {
            margin-top: 0;
            color: var(--vscode-textLink-foreground);
        }
    </style>
</head>
<body>
    <h3>Thekedar AI Harness</h3>
    <p>Your headless development orchestrator is active.</p>

    <div class="card">
        <strong>Active Connection:</strong><br>
        <span id="dashboard-link">${dashboardUrl}</span>
    </div>

    <button class="btn" onclick="openDashboard()">Open Dashboard Hub</button>
    <button class="btn" onclick="triggerDoctor()">Run Health Doctor</button>

    <script>
        const vscode = acquireVsCodeApi();
        function openDashboard() {
            vscode.postMessage({ command: 'openDashboard' });
        }
        function triggerDoctor() {
            vscode.postMessage({ command: 'triggerDoctor' });
        }
    </script>
</body>
</html>`;
    }
}
export function registerSidebar(context: vscode.ExtensionContext) {
    const provider = new ThekedarSidebarProvider();
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(ThekedarSidebarProvider.viewType, provider)
    );

    // Handle messages from the webview
    provider.resolveWebviewView = (original => function(webviewView, contextInfo, token) {
        webviewView.webview.onDidReceiveMessage(message => {
            switch (message.command) {
                case 'openDashboard':
                    const config = vscode.workspace.getConfiguration('thekedar');
                    const url = config.get<string>('dashboardUrl', 'http://localhost:8081');
                    vscode.env.openExternal(vscode.Uri.parse(url));
                    break;
                case 'triggerDoctor':
                    const terminal = vscode.window.createTerminal('Thekedar Doctor');
                    terminal.show();
                    terminal.sendText('uv run python -m thekedar_cli doctor');
                    break;
            }
        });
        return original.apply(provider, [webviewView, contextInfo, token]);
    })(provider.resolveWebviewView);
}
