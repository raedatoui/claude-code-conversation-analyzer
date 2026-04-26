export default function EmptyState({
    message = "Try adjusting your search or filters.",
}: {
    message?: string;
}) {
    return (
        <div className="flex flex-col items-center justify-center py-20 text-text-secondary">
            <svg
                className="w-12 h-12 mb-4 opacity-40"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
            >
                <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
            </svg>
            <h3 className="text-lg font-medium text-text-primary mb-1">
                No results found
            </h3>
            <p className="text-sm">{message}</p>
        </div>
    );
}
