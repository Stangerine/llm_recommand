interface Props {
  rating: number;
  count?: number;
  size?: "sm" | "md";
}

export function ProductRating({ rating, count, size = "sm" }: Props) {
  const sizeClasses = {
    sm: "text-xs",
    md: "text-sm",
  };

  return (
    <div
      className={`flex items-center gap-1 ${sizeClasses[size]} text-slate-500`}
    >
      <span className="text-amber-400">★</span>
      <span className="font-medium">{rating.toFixed(1)}</span>
      {count && (
        <span className="text-slate-400">({count.toLocaleString()})</span>
      )}
    </div>
  );
}
