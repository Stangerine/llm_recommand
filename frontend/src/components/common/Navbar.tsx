import { Link, useLocation } from "react-router-dom";

export function Navbar() {
  const location = useLocation();

  const links = [
    { path: "/", label: "推荐", icon: "✦" },
    { path: "/products", label: "商品", icon: "▦" },
    { path: "/search", label: "搜索", icon: "◎" },
    { path: "/simulator", label: "模拟器", icon: "⟳" },
  ];

  return (
    <header className="sticky top-0 z-50 w-full glass border-b border-slate-200/60">
      <div className="max-w-screen-xl mx-auto flex h-16 items-center px-6">
        {/* Logo */}
        <Link to="/" className="mr-8 flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-sm group-hover:shadow-glow transition-shadow duration-300">
            <span className="text-white text-sm font-bold">R</span>
          </div>
          <span className="font-semibold text-slate-800 tracking-tight">
            推荐系统
          </span>
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          {links.map((link) => {
            const isActive = location.pathname === link.path;
            return (
              <Link
                key={link.path}
                to={link.path}
                className={`
                  relative flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium
                  transition-all duration-150 ease-out
                  ${
                    isActive
                      ? "text-brand-700 bg-brand-50"
                      : "text-slate-500 hover:text-slate-800 hover:bg-slate-100"
                  }
                `}
              >
                <span className="text-xs opacity-70">{link.icon}</span>
                {link.label}
                {isActive && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-0.5 bg-brand-500 rounded-full" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Right side accent */}
        <div className="ml-auto flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-medium text-emerald-700">在线</span>
          </div>
        </div>
      </div>
    </header>
  );
}
