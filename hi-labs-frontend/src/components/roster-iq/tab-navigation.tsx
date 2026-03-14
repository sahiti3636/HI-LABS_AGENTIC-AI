"use client"

import React from "react"
import { motion } from "framer-motion"
import { MessageSquare, LayoutDashboard } from "lucide-react"

interface TabNavigationProps {
    activeTab: "chat" | "dashboard"
    onTabChange: (tab: "chat" | "dashboard") => void
}

export const TabNavigation: React.FC<TabNavigationProps> = ({ activeTab, onTabChange }) => {
    return (
        <div className="flex items-center gap-1 bg-muted/30 p-1 rounded-xl border border-border">
            <button
                onClick={() => onTabChange("chat")}
                className={`relative flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${activeTab === "chat" ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                    }`}
            >
                {activeTab === "chat" && (
                    <motion.div
                        layoutId="active-tab"
                        className="absolute inset-0 bg-background rounded-lg shadow-sm"
                        transition={{ type: "spring", bounce: 0.2, duration: 0.5 }}
                    />
                )}
                <MessageSquare className="h-4 w-4 relative z-10" />
                <span className="relative z-10">Chat Console</span>
            </button>
            <button
                onClick={() => onTabChange("dashboard")}
                className={`relative flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${activeTab === "dashboard" ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                    }`}
            >
                {activeTab === "dashboard" && (
                    <motion.div
                        layoutId="active-tab"
                        className="absolute inset-0 bg-background rounded-lg shadow-sm"
                        transition={{ type: "spring", bounce: 0.2, duration: 0.5 }}
                    />
                )}
                <LayoutDashboard className="h-4 w-4 relative z-10" />
                <span className="relative z-10">Live Dashboard</span>
            </button>
        </div>
    )
}
