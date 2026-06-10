"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar";
import { ChevronRight, Settings, LogOut, Cpu } from "lucide-react";
import { apiGet, clearAuthToken } from "@/lib/api";
import type {
  Project,
  ReadinessResponse,
  ReadinessStatus,
  S3ReadinessDetail,
  UseCase,
} from "@/lib/types";

// ─── Stage config ────────────────────────────────────────────────────────────

const STAGES = [
  { id: "s1", label: "Assessment", path: "stage1" },
  { id: "s2", label: "Complexity", path: "stage2" },
  { id: "s3", label: "Timeline", path: "stage3" },
  { id: "s4", label: "Sprint Tracker", path: "stage4" },
] as const;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function statusDot(status: string) {
  const classes: Record<string, string> = {
    not_ready: "bg-muted-foreground/40",
    ready: "bg-blue-500",
    running: "bg-primary animate-pulse",
    complete: "bg-green-500",
    stale: "bg-amber-500",
  };
  return classes[status] ?? classes.not_ready;
}

// ─── Types ───────────────────────────────────────────────────────────────────

interface ProjectWithUseCases extends Project {
  loadedUseCases: UseCase[];
  readiness: Record<string, ReadinessResponse>;
}

// ─── Skeleton ────────────────────────────────────────────────────────────────

function ProjectSkeleton() {
  return (
    <>
      {[1, 2, 3].map((i) => (
        <SidebarMenuItem key={i}>
          <SidebarMenuSkeleton showIcon />
        </SidebarMenuItem>
      ))}
    </>
  );
}

// ─── ProjectItem ─────────────────────────────────────────────────────────────

interface ProjectItemProps {
  project: ProjectWithUseCases;
  pathname: string;
  onReadinessUpdate: (
    projectId: string,
    ucId: string,
    readiness: ReadinessResponse,
  ) => void;
}

function ProjectItem({
  project,
  pathname,
  onReadinessUpdate,
}: ProjectItemProps) {
  const isProjectActive = pathname.startsWith(`/projects/${project.id}`);
  const [open, setOpen] = useState(isProjectActive);
  const firstUc = project.loadedUseCases[0];

  // Poll running stages every 5 s
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const runningUcs = project.loadedUseCases.filter((uc) => {
      const r = project.readiness[uc.id];
      if (!r) return false;
      return Object.values(r).some((s) => s === "running");
    });

    if (runningUcs.length > 0) {
      pollRef.current = setInterval(async () => {
        for (const uc of runningUcs) {
          try {
            const r = await apiGet<ReadinessResponse>(
              `/api/v1/use-cases/${uc.id}/readiness`,
            );
            onReadinessUpdate(project.id, uc.id, r);
          } catch {
            // silent — don't crash the sidebar on transient errors
          }
        }
      }, 5000);
    }

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [
    project.loadedUseCases,
    project.readiness,
    project.id,
    onReadinessUpdate,
  ]);

  return (
    <SidebarMenuItem>
      {/* Collapsible trigger row */}
      <SidebarMenuButton
        isActive={isProjectActive}
        onClick={() => setOpen((v) => !v)}
        className="group/project"
      >
        <ChevronRight
          className={`size-3.5 shrink-0 transition-transform duration-150 ${open ? "rotate-90" : ""}`}
        />
        <span className="truncate">{project.name}</span>
      </SidebarMenuButton>

      {/* Sub-menu */}
      {open && (
        <SidebarMenuSub>
          {project.loadedUseCases.length === 0 ? (
            <SidebarMenuSubItem>
              <SidebarMenuSubButton
                render={<Link href={`/projects/${project.id}`} />}
                className="italic text-muted-foreground"
              >
                Add use-case
              </SidebarMenuSubButton>
            </SidebarMenuSubItem>
          ) : (
            STAGES.map((stage) => {
              const href = firstUc
                ? `/projects/${project.id}/${stage.path}/${firstUc.id}`
                : `/projects/${project.id}`;

              const stageKey = stage.id as keyof ReadinessResponse;
              const readinessForUc = firstUc
                ? project.readiness[firstUc.id]
                : undefined;
              const rawStatus = readinessForUc
                ? (readinessForUc[stageKey] ?? "not_ready")
                : "not_ready";
              const status: ReadinessStatus =
                stage.id === "s3"
                  ? ((rawStatus as S3ReadinessDetail)?.phase_calculator ??
                    "not_ready")
                  : (rawStatus as ReadinessStatus);
              const isActive = pathname.startsWith(
                `/projects/${project.id}/${stage.path}`,
              );

              return (
                <SidebarMenuSubItem key={stage.id}>
                  <SidebarMenuSubButton
                    render={<Link href={href} />}
                    isActive={isActive}
                  >
                    <span
                      className={`inline-block size-2 shrink-0 rounded-full ${statusDot(status)}`}
                      aria-hidden="true"
                    />
                    <span>{stage.label}</span>
                  </SidebarMenuSubButton>
                </SidebarMenuSubItem>
              );
            })
          )}
        </SidebarMenuSub>
      )}
    </SidebarMenuItem>
  );
}

// ─── AppSidebar ───────────────────────────────────────────────────────────────

export function AppSidebar() {
  const router = useRouter();
  const pathname = usePathname();

  const [projects, setProjects] = useState<ProjectWithUseCases[]>([]);
  const [loading, setLoading] = useState(true);
  const [userEmail, setUserEmail] = useState<string>("");

  // Load user email from localStorage (stored at login)
  useEffect(() => {
    if (typeof window !== "undefined") {
      setUserEmail(localStorage.getItem("user_email") ?? "");
    }
  }, []);

  // Load projects + use-cases + initial readiness
  useEffect(() => {
    const load = async () => {
      try {
        const rawProjects = await apiGet<Project[]>("/api/v1/projects");

        const enriched = await Promise.all(
          rawProjects.map(async (p) => {
            let useCases: UseCase[] = [];
            try {
              useCases = await apiGet<UseCase[]>(
                `/api/v1/projects/${p.id}/use-cases`,
              );
            } catch {
              // project might have no use-cases endpoint yet
            }

            const readiness: Record<string, ReadinessResponse> = {};
            await Promise.all(
              useCases.map(async (uc) => {
                try {
                  readiness[uc.id] = await apiGet<ReadinessResponse>(
                    `/api/v1/use-cases/${uc.id}/readiness`,
                  );
                } catch {
                  // ignore
                }
              }),
            );

            return { ...p, loadedUseCases: useCases, readiness };
          }),
        );

        setProjects(enriched);
      } catch {
        // Auth error handled by page-level guards; sidebar stays empty
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const handleReadinessUpdate = (
    projectId: string,
    ucId: string,
    readiness: ReadinessResponse,
  ) => {
    setProjects((prev) =>
      prev.map((p) =>
        p.id === projectId
          ? { ...p, readiness: { ...p.readiness, [ucId]: readiness } }
          : p,
      ),
    );
  };

  const handleLogout = () => {
    clearAuthToken();
    if (typeof window !== "undefined") {
      localStorage.removeItem("user_email");
    }
    router.push("/auth/login");
  };

  const isSettingsActive = pathname.startsWith("/settings");

  return (
    <Sidebar collapsible="icon">
      {/* ── Logo ──────────────────────────────────────────────────────────── */}
      <SidebarHeader className="px-3 py-4">
        <Link
          href="/projects"
          className="flex items-center gap-2.5 rounded-md px-1 py-1 transition-colors hover:bg-sidebar-accent"
        >
          <Image
            alt="VectorIQ"
            src="/logo.png"
            width={480}
            height={80}
            className="h-20 w-auto group-data-[collapsible=icon]:hidden"
          />
        </Link>
      </SidebarHeader>

      {/* ── Projects tree ─────────────────────────────────────────────────── */}
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Projects</SidebarGroupLabel>
          <SidebarMenu>
            {loading ? (
              <ProjectSkeleton />
            ) : projects.length === 0 ? (
              <SidebarMenuItem>
                <SidebarMenuButton render={<Link href="/projects/new" />}>
                  <span className="text-muted-foreground">New project…</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ) : (
              projects.map((project) => (
                <ProjectItem
                  key={project.id}
                  project={project}
                  pathname={pathname}
                  onReadinessUpdate={handleReadinessUpdate}
                />
              ))
            )}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <SidebarFooter className="gap-1">
        {/* Settings */}
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              isActive={isSettingsActive}
              render={<Link href="/settings" />}
              tooltip="Settings"
            >
              <Settings className="size-4 shrink-0" />
              <span>Settings</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>

        {/* User + logout */}
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={handleLogout}
              tooltip="Sign out"
              className="text-muted-foreground hover:text-foreground"
            >
              <LogOut className="size-4 shrink-0" />
              <span className="truncate">{userEmail || "Sign out"}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
