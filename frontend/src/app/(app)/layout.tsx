import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/layout/AppSidebar"
import { Toaster } from "@/components/ui/sonner"

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <main className="flex-1 min-h-screen">
          {children}
        </main>
      </SidebarInset>
      <Toaster position="bottom-right" theme="dark" />
    </SidebarProvider>
  )
}
