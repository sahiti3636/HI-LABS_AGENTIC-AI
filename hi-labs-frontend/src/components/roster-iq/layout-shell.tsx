"use client"

import React, { useState } from "react"
import { Icons } from "@/components/ui/icons"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { TabNavigation } from "./tab-navigation"
import { ScannerCardStream } from "@/components/ui/scanner-card-stream"
import { SessionMemorySidebar } from "./session-memory"
import { ProcedurePanel } from "./procedure-panel"
import { AlertFeed } from "./alert-feed"
import { ChatInterface } from "./chat-interface"
import { Dashboard1 } from "@/components/ui/dashboard-1"
import { HeroSection } from "@/components/ui/hero-section"
import { LiquidButton } from "@/components/ui/liquid-glass-button"
import { BackgroundGradientGlow } from "@/components/ui/background-gradient-glow"

export const LayoutShell = () => {
    const [view, setView] = useState<"landing" | "dashboard">("landing")
    const [activeTab, setActiveTab] = useState<"chat" | "dashboard">("chat")

    if (view === "landing") {
        return (
            <div className="min-h-screen bg-background">
                <HeroSection />
                <div className="flex justify-center pb-20">
                    <LiquidButton className="px-14 h-16 text-xl font-bold" onClick={() => setView("dashboard")}>
                        Enter Agent Console
                    </LiquidButton>
                </div>
            </div>
        )
    }

    return (
        <div className="flex h-screen bg-background text-foreground overflow-hidden">
            {/* Sidebar Navigation - Shared */}
            <aside className="w-16 flex flex-col items-center py-6 border-r border-white/10 bg-black gap-8 shrink-0 relative z-20 shadow-2xl">
                <div className="h-10 w-10 rounded-xl bg-brand flex items-center justify-center shadow-lg shadow-brand/20">
                    <Icons.brain className="h-6 w-6 text-black" />
                </div>
                <nav className="flex flex-col gap-4">
                    <Button size="icon" variant="ghost" className={`h-10 w-10 text-white transition-all ${activeTab === "chat" ? "bg-white/20 shadow-inner scale-110" : "hover:bg-white/10"}`} onClick={() => setActiveTab("chat")}>
                        <Icons.activity className="h-5 w-5" />
                    </Button>
                    <Button size="icon" variant="ghost" className={`h-10 w-10 text-white transition-all ${activeTab === "dashboard" ? "bg-white/20 shadow-inner scale-110" : "hover:bg-white/10"}`} onClick={() => setActiveTab("dashboard")}>
                        <Icons.database className="h-5 w-5" />
                    </Button>
                    <Button size="icon" variant="ghost" className="h-10 w-10 text-white/70 hover:bg-white/10 transition-colors">
                        <Icons.history className="h-5 w-5" />
                    </Button>
                </nav>
                <div className="mt-auto flex flex-col gap-4">
                    <Button size="icon" variant="ghost" className="h-10 w-10 text-white/70 hover:bg-white/10 transition-colors">
                        <Icons.settings className="h-5 w-5" />
                    </Button>
                    <div className="h-10 w-10 rounded-full border border-white/20 bg-white/10 shadow-inner overflow-hidden">
                        <Avatar className="h-full w-full">
                            <AvatarFallback className="text-[10px] text-white">SP</AvatarFallback>
                        </Avatar>
                    </div>
                </div>
            </aside>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0 relative">
                {/* Header */}
                <header className="h-16 border-b border-white/10 flex items-center justify-between px-8 bg-black/90 backdrop-blur-md shrink-0 z-30 shadow-md">
                    <div className="flex items-center gap-6 text-white">
                        <TabNavigation activeTab={activeTab} onTabChange={(t) => setActiveTab(t)} />
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/10 border border-white/20 backdrop-blur-sm">
                            <div className="h-2 w-2 rounded-full bg-brand animate-pulse" />
                            <span className="text-[10px] font-bold text-white uppercase tracking-wider">Agent Live</span>
                        </div>
                        <Button variant="outline" size="sm" className="text-xs border-white/20 bg-white/5 hover:bg-white/10 text-white hidden md:flex" onClick={() => setView("landing")}>Logout</Button>
                    </div>
                </header>

                <main className="flex-1 flex overflow-hidden relative">
                    {activeTab === "chat" ? (
                        /* Chat Console - Occupies full center part */
                        <div className="flex-1 relative">
                            <ChatInterface />
                        </div>
                    ) : (
                        /* Dashboard View - Analytical tools and tiles */
                        <BackgroundGradientGlow className="flex-1 flex overflow-hidden">
                            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar relative z-10">
                                <Dashboard1 />
                            </div>

                            {/* Dashboard Side Panels */}
                            <aside className="w-80 border-l border-black/5 bg-white/30 backdrop-blur-md flex flex-col shrink-0 relative z-10">
                                <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-4">
                                    <div className="p-2">
                                        <ScannerCardStream />
                                    </div>
                                    <SessionMemorySidebar />
                                    <ProcedurePanel />
                                    <AlertFeed />
                                </div>
                            </aside>
                        </BackgroundGradientGlow>
                    )}
                </main>
            </div>
        </div>
    )
}
