/**
 * Main application layout with navigation and role-aware menu.
 */

import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui';

export function Layout() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="layout">
      <header className="layout__header">
        <div className="layout__container">
          <div className="layout__brand">
            <Link to="/" className="layout__logo">
              Loan Origination System
            </Link>
          </div>

          {isAuthenticated && (
            <nav className="layout__nav" aria-label="Main navigation">
              <ul className="layout__nav-list">
                <li>
                  <Link to="/" className="layout__nav-link">
                    Home
                  </Link>
                </li>
                <li>
                  <Link to="/applications/new" className="layout__nav-link">
                    New Application
                  </Link>
                </li>
                {user?.groups.includes('Operator') && (
                  <li>
                    <Link to="/admin" className="layout__nav-link">
                      Admin
                    </Link>
                  </li>
                )}
              </ul>
            </nav>
          )}

          <div className="layout__user">
            {isAuthenticated ? (
              <>
                <span className="layout__username">
                  {user?.email || user?.username}
                </span>
                <Button variant="secondary" size="sm" onClick={handleLogout}>
                  Logout
                </Button>
              </>
            ) : (
              <Link to="/login" className="layout__nav-link">
                Login
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="layout__main">
        <div className="layout__container">
          <Outlet />
        </div>
      </main>

      <footer className="layout__footer">
        <div className="layout__container">
          <p>&copy; 2026 Loan Origination System. Demo environment.</p>
        </div>
      </footer>
    </div>
  );
}
