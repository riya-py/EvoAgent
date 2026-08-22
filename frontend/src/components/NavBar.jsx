import { NavLink } from 'react-router-dom'

const linkStyle = ({ isActive }) => ({
  fontFamily: 'var(--font-display)',
  fontSize: 13,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  textDecoration: 'none',
  padding: '0.5rem 0.9rem',
  borderRadius: 'var(--radius)',
  color: isActive ? 'var(--void)' : 'var(--chalk-dim)',
  background: isActive ? 'var(--gold)' : 'transparent',
})

export default function NavBar() {
  return (
    <header
      style={{
        borderBottom: '1px solid var(--void-line)',
        background: 'var(--void-raised)',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}
    >
      <div
        className="page"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '0.9rem', paddingBottom: '0.9rem' }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.6rem' }}>
          <h1 style={{ fontSize: 20, letterSpacing: '0.04em' }}>EvoAgent</h1>
          <span className="eyebrow">8 personalities · evolving roster</span>
        </div>
        <nav style={{ display: 'flex', gap: '0.4rem' }}>
          <NavLink to="/" style={linkStyle} end>
            Agent
          </NavLink>
          <NavLink to="/compare" style={linkStyle}>
            Compare
          </NavLink>
        </nav>
      </div>
    </header>
  )
}