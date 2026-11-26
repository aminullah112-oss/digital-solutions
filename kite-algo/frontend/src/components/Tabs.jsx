// A simple accessible tab bar. Left/Right arrow keys move between tabs.
export default function Tabs({ tabs, activeId, onChange }) {
  function handleKeyDown(e) {
    const i = tabs.findIndex((t) => t.id === activeId);
    let next = null;
    if (e.key === "ArrowRight") next = tabs[(i + 1) % tabs.length];
    if (e.key === "ArrowLeft") next = tabs[(i - 1 + tabs.length) % tabs.length];
    if (next) {
      e.preventDefault();
      onChange(next.id);
      document.getElementById(`tab-${next.id}`)?.focus();
    }
  }

  return (
    <div className="tabs" role="tablist" aria-label="Dashboard sections" onKeyDown={handleKeyDown}>
      {tabs.map((tab) => {
        const selected = tab.id === activeId;
        return (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            role="tab"
            type="button"
            aria-selected={selected}
            aria-controls={`panel-${tab.id}`}
            tabIndex={selected ? 0 : -1}
            className={`tab${selected ? " tab-active" : ""}`}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
