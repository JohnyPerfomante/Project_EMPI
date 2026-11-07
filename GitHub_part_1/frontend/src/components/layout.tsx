import {
  Bell,
  BookOpen,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  FileStack,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Settings2,
  UsersRound,
  X,
} from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Brand } from "../features/auth";
import { usePage } from "../lib/api";
import { initials, roleLabels } from "../lib/format";
import type { Submission, User } from "../lib/types";

const learning = [
  { path: "/", title: "Огляд", icon: LayoutDashboard },
  { path: "/courses", title: "Дисципліни", icon: BookOpen },
  { path: "/questions", title: "Банк питань", icon: FileStack },
  { path: "/submissions", title: "Перевірка відповідей", icon: ClipboardCheck },
  { path: "/variations", title: "База варіацій", icon: ScrollText },
];
const admin = [
  { path: "/admin/users", title: "Користувачі", icon: UsersRound },
  { path: "/admin/catalog", title: "Довідники", icon: BookOpen },
  { path: "/admin/settings", title: "Налаштування NLP", icon: Settings2 },
  { path: "/admin/audit", title: "Журнал аудиту", icon: ScrollText },
];
const student = [
  learning[0],
  learning[1],
  { ...learning[2], title: "Завдання" },
  { ...learning[3], title: "Мої відповіді" },
];

export function Layout({
  user,
  logout,
}: {
  user: User;
  logout: () => Promise<void>;
}) {
  const [menu, setMenu] = useState(false);
  const [popover, setPopover] = useState<"alerts" | "profile" | null>(null);
  const [logoutError, setLogoutError] = useState("");
  const location = useLocation();
  const navigation = user.role === "student" ? student : learning;
  const pending = usePage<Submission>(
    "/reviews/pending",
    { limit: 1 },
    user.role !== "student",
    20_000,
  );
  const section = [...navigation, ...admin].find((item) =>
    item.path === "/"
      ? location.pathname === "/"
      : location.pathname === item.path ||
        location.pathname.startsWith(item.path + "/"),
  );
  const close = () => {
    setMenu(false);
    setPopover(null);
  };
  const links = (items: typeof learning) =>
    items.map(({ path, title, icon: Icon }) => (
      <NavLink key={path} to={path} end={path === "/"} onClick={close}>
        <Icon size={18} />
        <span>{title}</span>
      </NavLink>
    ));
  return (
    <div className="app-layout">
      {menu && (
        <button
          className="mobile-backdrop"
          aria-label="Закрити меню"
          onClick={close}
        />
      )}
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <Link to="/" onClick={close} className="brand-link">
          <Brand />
        </Link>
        <nav aria-label="Головне меню">
          <p className="nav-label">НАВЧАННЯ</p>
          {links(navigation)}
          {user.role === "admin" && (
            <>
              <p className="nav-label">АДМІНІСТРУВАННЯ</p>
              {links(admin)}
            </>
          )}
        </nav>
        <div className="sidebar-footer">
          <div className="school-mark">НТУ</div>
          <div>
            <strong>НТУ</strong>
            <small>Навчальний кабінет</small>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              aria-label={menu ? "Закрити меню" : "Відкрити меню"}
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X size={21} /> : <Menu size={21} />}
            </button>
            <div className="breadcrumbs">
              <Link to="/" onClick={close}>
                Кабінет
              </Link>
              <ChevronRight size={15} />
              <strong>{section?.title ?? "Сторінка"}</strong>
            </div>
          </div>
          <div className="top-actions">
            {user.role !== "student" && (
              <div className="popover-anchor">
                <button
                  className="icon-button bell"
                  aria-label="Сповіщення"
                  aria-expanded={popover === "alerts"}
                  onClick={() =>
                    setPopover(popover === "alerts" ? null : "alerts")
                  }
                >
                  <Bell size={19} />
                  {!!pending.data?.total && <i />}
                </button>
                {popover === "alerts" && (
                  <div className="popover">
                    <strong>Сповіщення</strong>
                    <p>
                      {pending.isError
                        ? "Сповіщення тимчасово недоступні."
                        : `Очікують рішення: ${pending.data?.total ?? 0}`}
                    </p>
                    <Link
                      to="/submissions?review_status=pending"
                      onClick={close}
                    >
                      Відкрити центр перевірки
                    </Link>
                  </div>
                )}
              </div>
            )}
            <div className="popover-anchor">
              <button
                className="profile"
                aria-label="Профіль користувача"
                aria-expanded={popover === "profile"}
                onClick={() =>
                  setPopover(popover === "profile" ? null : "profile")
                }
              >
                <span className="avatar">{initials(user.full_name)}</span>
                <span className="profile-name">
                  <strong>{user.full_name}</strong>
                  <small>{roleLabels[user.role]}</small>
                </span>
                <ChevronDown size={14} />
              </button>
              {popover === "profile" && (
                <div className="popover">
                  <strong>{user.full_name}</strong>
                  <p>{user.email}</p>
                  {logoutError && <p role="alert">{logoutError}</p>}
                  <button
                    className="button secondary"
                    onClick={() =>
                      logout().catch(() =>
                        setLogoutError(
                          "Не вдалося завершити сесію. Повторіть спробу.",
                        ),
                      )
                    }
                  >
                    <LogOut size={16} /> Вийти
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className="content" key={location.pathname + location.search}>
          <Outlet context={user} />
        </main>
      </div>
    </div>
  );
}
