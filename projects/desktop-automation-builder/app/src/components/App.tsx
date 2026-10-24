import { useState } from 'react';
import { RunView } from './RunView';
import { ScriptsManager } from './ScriptsManager';
import { WorkflowEditor } from './WorkflowEditor';
import { WorkflowsList } from './WorkflowsList';

type Route =
  | { view: 'workflows' }
  | { view: 'editor'; workflowId: string }
  | { view: 'scripts' }
  | { view: 'run'; workflowId: string };

export function App() {
  const [route, setRoute] = useState<Route>({ view: 'workflows' });

  const goWorkflows = () => setRoute({ view: 'workflows' });
  const goRun = (workflowId: string) => setRoute({ view: 'run', workflowId });

  return (
    <div className="app">
      <header className="app-header">
        <h1>Desktop Automation Builder</h1>
        <nav aria-label="Primary">
          <button
            type="button"
            onClick={goWorkflows}
            aria-current={route.view === 'workflows' ? 'page' : undefined}
          >
            Workflows
          </button>
          <button
            type="button"
            onClick={() => setRoute({ view: 'scripts' })}
            aria-current={route.view === 'scripts' ? 'page' : undefined}
          >
            Approved scripts
          </button>
        </nav>
      </header>
      <main className="app-main">
        {route.view === 'workflows' && (
          <WorkflowsList
            onOpen={(id) => setRoute({ view: 'editor', workflowId: id })}
            onRun={goRun}
          />
        )}
        {route.view === 'editor' && (
          <WorkflowEditor
            workflowId={route.workflowId}
            onBack={goWorkflows}
            onRun={goRun}
          />
        )}
        {route.view === 'scripts' && <ScriptsManager />}
        {route.view === 'run' && (
          <RunView workflowId={route.workflowId} onBack={goWorkflows} />
        )}
      </main>
    </div>
  );
}
