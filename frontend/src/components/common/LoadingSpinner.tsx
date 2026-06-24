export function LoadingSpinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const sizeClasses = {
    sm: "h-4 w-4",
    md: "h-8 w-8",
    lg: "h-12 w-12",
  };

  return (
    <div className="flex flex-col items-center justify-center p-8 gap-3">
      <div className="relative">
        <div
          className={`${sizeClasses[size]} animate-spin rounded-full border-2 border-slate-200 border-t-brand-500`}
        />
        <div
          className={`absolute inset-0 ${sizeClasses[size]} animate-spin rounded-full border-2 border-transparent border-b-brand-300`}
          style={{ animationDirection: "reverse", animationDuration: "1.5s" }}
        />
      </div>
      <span className="text-xs text-slate-400 animate-pulse">加载中...</span>
    </div>
  );
}
