import { getGradeColors } from "@/lib/utils";

export default function GradeBadge({
    grade,
    score,
}: {
    grade: string;
    score?: number;
}) {
    const colors = getGradeColors(grade);
    return (
        <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-sm font-bold ${colors.bg} ${colors.text} border ${colors.border}`}
        >
            {grade}
            {score !== undefined && (
                <span className="font-normal opacity-75">
                    {score.toFixed(0)}
                </span>
            )}
        </span>
    );
}
