import React from "react";
import { cn } from "@/lib/utils";

const Mockup = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement> & { type?: "desktop" | "mobile" }
>(({ className, type = "desktop", children, ...props }, ref) => (
    <div
        ref={ref}
        className={cn(
            "relative rounded-xl border bg-background shadow-2xl",
            type === "desktop" ? "aspect-video w-full" : "aspect-[9/19] w-full max-w-[300px]",
            className,
        )}
        {...props}
    >
        <div className="flex items-center gap-1.5 border-b px-4 py-2">
            <div className="h-2 w-2 rounded-full bg-red-500/50" />
            <div className="h-2 w-2 rounded-full bg-amber-500/50" />
            <div className="h-2 w-2 rounded-full bg-emerald-500/50" />
        </div>
        <div className="h-[calc(100%-33px)] overflow-hidden rounded-b-xl">
            {children}
        </div>
    </div>
));
Mockup.displayName = "Mockup";

export { Mockup };
