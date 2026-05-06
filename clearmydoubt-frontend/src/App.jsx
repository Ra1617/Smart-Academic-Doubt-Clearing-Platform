import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { GraduationCap, ShieldCheck, Database, LogOut, Send } from 'lucide-react';
import './App.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:4000';
const TOKEN_KEY = 'cmd_auth';

const toErrorMessage = (value, fallback) => {
  if (!value) return fallback;
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) {
    const msgs = value
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item.msg === 'string') return item.msg;
        try {
          return JSON.stringify(item);
        } catch {
          return null;
        }
      })
      .filter(Boolean);
    return msgs.length ? msgs.join('; ') : fallback;
  }
  if (typeof value === 'object') {
    if (typeof value.msg === 'string') return value.msg;
    if (typeof value.detail === 'string') return value.detail;
    try {
      return JSON.stringify(value);
    } catch {
      return fallback;
    }
  }
  return String(value);
};

const tryPost = async (paths, body, config = {}) => {
  let lastError = null;
  for (const path of paths) {
    try {
      return await axios.post(`${API_BASE_URL}${path}`, body, config);
    } catch (error) {
      lastError = error;
      if (error?.response?.status === 404) continue;
      throw error;
    }
  }
  throw lastError || new Error('No matching endpoint found');
};

const tryGet = async (paths, config = {}) => {
  let lastError = null;
  for (const path of paths) {
    try {
      return await axios.get(`${API_BASE_URL}${path}`, config);
    } catch (error) {
      lastError = error;
      if (error?.response?.status === 404) continue;
      throw error;
    }
  }
  throw lastError || new Error('No matching endpoint found');
};

function App() {
  const [apiState, setApiState] = useState({ loading: true, ok: false, message: '' });
  const [auth, setAuth] = useState(() => {
    const raw = localStorage.getItem(TOKEN_KEY);
    return raw ? JSON.parse(raw) : null;
  });

  const [notice, setNotice] = useState({ type: '', message: '' });

  const [login, setLogin] = useState({ email: '', password: '' });
  const [register, setRegister] = useState({
    full_name: '',
    email: '',
    password: '',
    roll_number: '',
    department: '',
    semester: '',
    phone: '',
  });

  const [doubt, setDoubt] = useState({
    title: '',
    description: '',
    subject: '',
    priority: 1,
  });
  const [doubts, setDoubts] = useState([]);
  const [loadingDoubts, setLoadingDoubts] = useState(false);

  const authHeader = useMemo(() => {
    if (!auth?.access_token) return {};
    return { Authorization: `Bearer ${auth.access_token}` };
  }, [auth]);

  useEffect(() => {
    checkBackend();
  }, []);

  useEffect(() => {
    if (auth?.role === 'student') {
      fetchMyDoubts();
    }
  }, [auth]);

  const pushNotice = (type, message) => {
    setNotice({ type, message });
  };

  const checkBackend = async () => {
    setApiState({ loading: true, ok: false, message: 'Checking backend...' });
    try {
      const root = await axios.get(`${API_BASE_URL}/`);
      setApiState({
        loading: false,
        ok: true,
        message: root?.data?.message || 'Backend reachable',
      });
    } catch {
      setApiState({ loading: false, ok: false, message: 'Backend not reachable' });
    }
  };

  const saveAuth = (tokenPayload) => {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(tokenPayload));
    setAuth(tokenPayload);
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setAuth(null);
    setDoubts([]);
    pushNotice('success', 'Logged out');
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    try {
      const response = await tryPost(['/auth/login', '/auth/auth/login'], login);
      saveAuth(response.data);
      pushNotice('success', `Welcome ${response.data.full_name || 'back'}`);
    } catch (error) {
      pushNotice('error', toErrorMessage(error?.response?.data?.detail, 'Login failed'));
    }
  };

  const handleRegister = async (event) => {
    event.preventDefault();
    const payload = {
      ...register,
      semester: register.semester ? Number(register.semester) : null,
    };

    try {
      const response = await tryPost(['/auth/register', '/auth/auth/register'], payload);
      saveAuth(response.data);
      pushNotice('success', 'Registration complete');
    } catch (error) {
      pushNotice('error', toErrorMessage(error?.response?.data?.detail, 'Registration failed'));
    }
  };

  const fetchMyDoubts = async () => {
    if (!auth?.access_token) return;
    setLoadingDoubts(true);
    try {
      const response = await tryGet(['/doubts/my', '/doubts/doubts/my'], {
        headers: authHeader,
      });
      setDoubts(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      pushNotice('error', toErrorMessage(error?.response?.data?.detail, 'Unable to load doubts'));
    } finally {
      setLoadingDoubts(false);
    }
  };

  const submitDoubt = async (event) => {
    event.preventDefault();
    if (!auth?.access_token) {
      pushNotice('error', 'Login as student first');
      return;
    }

    const formData = new FormData();
    formData.append('title', doubt.title);
    formData.append('description', doubt.description);
    formData.append('subject', doubt.subject);
    formData.append('priority', String(doubt.priority));

    try {
      await tryPost(['/doubts/', '/doubts/doubts/'], formData, {
        headers: {
          ...authHeader,
          'Content-Type': 'multipart/form-data',
        },
      });
      pushNotice('success', 'Doubt submitted');
      setDoubt({ title: '', description: '', subject: '', priority: 1 });
      fetchMyDoubts();
    } catch (error) {
      pushNotice('error', toErrorMessage(error?.response?.data?.detail, 'Submission failed'));
    }
  };

  return (
    <div className="app-shell">
      <header className="hero fade-in">
        <div>
          <p className="eyebrow">SEPM Project</p>
          <h1>Smart Academic Doubt Platform</h1>
          <p className="hero-copy">
            Student doubt posting, faculty resolution workflow, and AI similarity guidance from a single frontend.
          </p>
        </div>
        <div className="hero-chip-row">
          <span className={`chip ${apiState.ok ? 'ok' : 'bad'}`}>
            <Database size={16} />
            {apiState.loading ? 'Checking API...' : apiState.ok ? 'Backend Online' : 'Backend Offline'}
          </span>
          <span className="chip neutral">{API_BASE_URL}</span>
        </div>
      </header>

      {notice.message ? (
        <div className={`notice ${notice.type === 'error' ? 'error' : 'success'}`}>
          {notice.message}
        </div>
      ) : null}

      <main className="grid-wrap">
        <section className="card slide-up">
          <h2>
            <ShieldCheck size={18} />
            Access
          </h2>
          <p className="card-sub">Login with existing account.</p>
          <form className="form" onSubmit={handleLogin}>
            <label>
              Email
              <input
                type="email"
                value={login.email}
                onChange={(e) => setLogin((v) => ({ ...v, email: e.target.value }))}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={login.password}
                onChange={(e) => setLogin((v) => ({ ...v, password: e.target.value }))}
                required
              />
            </label>
            <button type="submit">Login</button>
          </form>
        </section>

        <section className="card slide-up delay-1">
          <h2>
            <GraduationCap size={18} />
            Student Registration
          </h2>
          <p className="card-sub">Create a student account for your project workflow.</p>
          <form className="form" onSubmit={handleRegister}>
            <label>
              Full Name
              <input
                type="text"
                value={register.full_name}
                onChange={(e) => setRegister((v) => ({ ...v, full_name: e.target.value }))}
                required
              />
            </label>
            <label>
              Email
              <input
                type="email"
                value={register.email}
                onChange={(e) => setRegister((v) => ({ ...v, email: e.target.value }))}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={register.password}
                onChange={(e) => setRegister((v) => ({ ...v, password: e.target.value }))}
                required
              />
            </label>
            <div className="two-col">
              <label>
                Roll Number
                <input
                  type="text"
                  value={register.roll_number}
                  onChange={(e) => setRegister((v) => ({ ...v, roll_number: e.target.value }))}
                />
              </label>
              <label>
                Semester
                <input
                  type="number"
                  min="1"
                  max="12"
                  value={register.semester}
                  onChange={(e) => setRegister((v) => ({ ...v, semester: e.target.value }))}
                />
              </label>
            </div>
            <div className="two-col">
              <label>
                Department
                <input
                  type="text"
                  value={register.department}
                  onChange={(e) => setRegister((v) => ({ ...v, department: e.target.value }))}
                />
              </label>
              <label>
                Phone
                <input
                  type="text"
                  value={register.phone}
                  onChange={(e) => setRegister((v) => ({ ...v, phone: e.target.value }))}
                />
              </label>
            </div>
            <button type="submit">Register Student</button>
          </form>
        </section>

        <section className="card wide slide-up delay-2">
          <div className="row-between">
            <h2>
              <Send size={18} />
              Student Workspace
            </h2>
            {auth && (
              <button type="button" className="ghost" onClick={logout}>
                <LogOut size={16} />
                Logout
              </button>
            )}
          </div>

          {auth ? (
            <>
              <p className="card-sub">
                Logged in as <strong>{auth.full_name || auth.email || 'User'}</strong> ({auth.role})
              </p>

              {auth.role === 'student' ? (
                <>
                  <form className="form" onSubmit={submitDoubt}>
                    <label>
                      Doubt Title
                      <input
                        type="text"
                        value={doubt.title}
                        onChange={(e) => setDoubt((v) => ({ ...v, title: e.target.value }))}
                        required
                      />
                    </label>
                    <label>
                      Description
                      <textarea
                        value={doubt.description}
                        onChange={(e) => setDoubt((v) => ({ ...v, description: e.target.value }))}
                        rows={4}
                        required
                      />
                    </label>
                    <div className="two-col">
                      <label>
                        Subject
                        <input
                          type="text"
                          value={doubt.subject}
                          onChange={(e) => setDoubt((v) => ({ ...v, subject: e.target.value }))}
                          required
                        />
                      </label>
                      <label>
                        Priority (1-5)
                        <input
                          type="number"
                          min="1"
                          max="5"
                          value={doubt.priority}
                          onChange={(e) => setDoubt((v) => ({ ...v, priority: Number(e.target.value) }))}
                          required
                        />
                      </label>
                    </div>
                    <button type="submit">Submit Doubt</button>
                  </form>

                  <div className="list-head">
                    <h3>My Doubts</h3>
                    <button type="button" className="secondary" onClick={fetchMyDoubts}>
                      Refresh
                    </button>
                  </div>

                  {loadingDoubts ? (
                    <p className="muted">Loading doubts...</p>
                  ) : doubts.length === 0 ? (
                    <p className="muted">No doubts yet.</p>
                  ) : (
                    <ul className="doubt-list">
                      {doubts.map((item) => (
                        <li key={item.id}>
                          <div>
                            <strong>{item.title}</strong>
                            <p>
                              {item.subject || 'General'} | {item.status} | Priority {item.priority}
                            </p>
                          </div>
                          <span>{new Date(item.created_at).toLocaleString()}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <p className="muted">This dashboard currently includes student actions. Faculty/Admin panels can be added next.</p>
              )}
            </>
          ) : (
            <p className="muted">Login or register to access the workspace.</p>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
