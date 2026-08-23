import type { DemoScenario } from "../demo/scenarios.js";

interface ScenarioPickerProps {
  scenarios: readonly DemoScenario[];
  selectedId: string | null;
  onSelect: (scenario: DemoScenario) => void;
  demoMode: boolean;
}

export function ScenarioPicker({
  scenarios,
  selectedId,
  onSelect,
  demoMode,
}: ScenarioPickerProps) {
  return (
    <section className="scenario-picker" aria-label="六个示范场景">
      <div className="scenario-picker-heading">
        <div>
          <span className="eyebrow">示范场景</span>
          <h2>选择示范任务</h2>
        </div>
        {demoMode && <span className="demo-badge">演示模式</span>}
      </div>
      <div className="scenario-card-list">
        {scenarios.map((scenario) => (
          <button
            type="button"
            className={`scenario-card ${selectedId === scenario.id ? "active" : ""}`}
            key={scenario.id}
            onClick={() => onSelect(scenario)}
            aria-pressed={selectedId === scenario.id}
          >
            <span className="scenario-card-title">{scenario.title}</span>
            <span className="scenario-card-description">{scenario.description}</span>
            <span className="scenario-card-tags">
              {scenario.tags.map((tag) => <span key={tag}>{tag}</span>)}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
