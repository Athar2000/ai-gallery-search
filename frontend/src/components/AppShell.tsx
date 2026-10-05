import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const navigation = [
  { to: "/", label: "Overview", icon: "OV" },
  { to: "/photos", label: "Photo library", icon: "PH" },
  { to: "/timeline", label: "Timeline", icon: "TL" },
  { to: "/albums", label: "Albums", icon: "AL" },
  { to: "/people", label: "People", icon: "PE" },
  { to: "/locations", label: "Locations", icon: "LO" },
  { to: "/smart-filters", label: "Smart filters", icon: "AI" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <Link to="/" className="brand-lockup">
          <span className="brand-mark">AG</span>
          <span>
            <strong>AtharVision AI</strong>
            <small>Search workspace</small>
          </span>
        </Link>

        <div className="sidebar-section-label">Workspace</div>
        <nav className="sidebar-nav" aria-label="Primary navigation">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <NavLink to="/settings" className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}>
            <span className="nav-icon">ST</span>
            <span>Settings</span>
          </NavLink>
          <div className="user-strip">
            <span className="avatar">{(user?.email?.[0] ?? "U").toUpperCase()}</span>
            <span className="user-copy">
              <strong>{user?.full_name || "Gallery owner"}</strong>
              <small>{user?.email}</small>
            </span>
            <button onClick={logout} className="logout-button" title="Log out">↗</button>
          </div>
        </div>
      </aside>

      <main className="app-main">
        <div className="mobile-header">
          <Link to="/" className="brand-lockup">
            <span className="brand-mark">AG</span>
            <strong>AtharVision AI</strong>
          </Link>
          <Link to="/settings" className="mobile-settings">Settings</Link>
        </div>
        <div className="workspace-bar">
          <div>
            <span className="eyebrow">Personal media workspace</span>
            <p>Organize, understand, and find every image.</p>
          </div>
          <span className="system-status"><i /> Index online</span>
        </div>
        {children}
      </main>
    </div>
  );
}
