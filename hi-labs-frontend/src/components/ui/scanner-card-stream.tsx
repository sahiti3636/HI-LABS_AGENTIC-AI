"use client";

import React, { useRef, useState, useMemo, useEffect } from "react";
import * as THREE from "three";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Icons } from "@/components/ui/icons";

const ParticleCanvas = () => {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!containerRef.current) return;

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });

        const updateSize = () => {
            if (!containerRef.current) return;
            const { clientWidth, clientHeight } = containerRef.current;
            renderer.setSize(clientWidth, clientHeight);
            camera.aspect = clientWidth / clientHeight;
            camera.updateProjectionMatrix();
        };

        updateSize();
        containerRef.current.appendChild(renderer.domElement);

        const particles = new THREE.BufferGeometry();
        const count = 1000;
        const positions = new Float32Array(count * 3);
        for (let i = 0; i < count * 3; i++) {
            positions[i] = (Math.random() - 0.5) * 10;
        }
        particles.setAttribute("position", new THREE.BufferAttribute(positions, 3));

        const material = new THREE.PointsMaterial({
            color: 0x3b82f6,
            size: 0.02,
            transparent: true,
            opacity: 0.5,
        });

        const points = new THREE.Points(particles, material);
        scene.add(points);
        camera.position.z = 5;

        let animationFrameId: number;
        const animate = () => {
            points.rotation.y += 0.001;
            points.rotation.x += 0.0005;
            renderer.render(scene, camera);
            animationFrameId = requestAnimationFrame(animate);
        };
        animate();

        const observer = new ResizeObserver(updateSize);
        observer.observe(containerRef.current);

        return () => {
            cancelAnimationFrame(animationFrameId);
            observer.disconnect();
            if (containerRef.current) {
                containerRef.current.removeChild(renderer.domElement);
            }
        };
    }, []);

    return <div ref={containerRef} className="absolute inset-0 z-0 opacity-40" />;
};

export const ScannerCardStream = () => {
    const [cards, setCards] = useState([
        { id: 1, title: "Roster #49283", status: "Ingesting", progress: 45 },
        { id: 2, title: "State IL Health", status: "Validating", progress: 82 },
        { id: 3, title: "Provider Map X", status: "Mapping", progress: 12 },
    ]);

    return (
        <div className="relative w-full max-w-md space-y-4 overflow-hidden p-6">
            <ParticleCanvas />
            <div className="relative z-10 space-y-4 font-mono">
                <AnimatePresence>
                    {cards.map((card, i) => (
                        <motion.div
                            key={card.id}
                            initial={{ opacity: 0, x: -20, scale: 0.95 }}
                            animate={{ opacity: 1, x: 0, scale: 1 }}
                            transition={{ delay: i * 0.1 }}
                        >
                            <Card className="border-brand/20 bg-background/50 backdrop-blur-md">
                                <div className="relative overflow-hidden p-4">
                                    <div className="absolute top-0 left-0 h-1 w-full bg-brand/10">
                                        <motion.div
                                            className="h-full bg-brand"
                                            initial={{ width: 0 }}
                                            animate={{ width: `${card.progress}%` }}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between gap-4">
                                        <div className="flex items-center gap-3">
                                            <Icons.fileText className="h-5 w-5 text-brand" />
                                            <div>
                                                <div className="text-sm font-bold uppercase tracking-wider">{card.title}</div>
                                                <div className="text-[10px] text-muted-foreground">{card.status}...</div>
                                            </div>
                                        </div>
                                        <Badge variant="outline" className="border-brand/50 text-brand">
                                            {card.progress}%
                                        </Badge>
                                    </div>
                                </div>
                            </Card>
                        </motion.div>
                    ))}
                </AnimatePresence>

                <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-background via-transparent to-background" />
                <div className="absolute inset-0 animate-scan-pulse border-y border-brand/20" />
            </div>
        </div>
    );
};
