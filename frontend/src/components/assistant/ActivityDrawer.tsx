import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { voxaraService } from '../../lib/voxaraService';
import type {
  OpportunityItem,
  SavedOpportunityItem,
  NotificationItem,
  ExecutionRecord,
  UserPreferencesItem,
  SchedulerStatus,
} from '../../lib/voxaraService';
import { useAuth } from '../../hooks/useAuth';
import {
  Compass,
  BookmarkCheck,
  Activity,
  Bell,
  ExternalLink,
  RefreshCw,
  AlertTriangle,
  Clock,
  Sparkles,
  ShieldCheck,
  Plus,
  Trash2,
  Sliders,
  Check,
  CheckCircle2,
  Search,
  CheckCheck,
  MapPin,
  AlertCircle,
  FileEdit,
  Save,
  X,
} from 'lucide-react';

export type DrawerTab = 'opportunities' | 'pipeline' | 'notifications' | 'preferences' | 'telemetry';

interface ActivityDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  activeTabDefault?: DrawerTab;
  onOpenAuth?: () => void;
}

export const ActivityDrawer: React.FC<ActivityDrawerProps> = ({
  isOpen,
  onClose,
  activeTabDefault = 'opportunities',
}) => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<DrawerTab>(activeTabDefault);

  // Data states
  const [opportunities, setOpportunities] = useState<OpportunityItem[]>([]);
  const [matchedOpportunities, setMatchedOpportunities] = useState<OpportunityItem[]>([]);
  const [savedOpportunities, setSavedOpportunities] = useState<SavedOpportunityItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [executions, setExecutions] = useState<ExecutionRecord[]>([]);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);

  // UI / Interaction states
  const [oppMode, setOppMode] = useState<'catalog' | 'matches'>('catalog');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [pipelineStatusFilter, setPipelineStatusFilter] = useState<string>('all');
  const [notifUnreadOnly, setNotifUnreadOnly] = useState<boolean>(false);

  // Editing notes state per saved item
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState<string>('');

  // Preference draft state
  const [prefDraft, setPrefDraft] = useState<UserPreferencesItem>({
    roles: ['AI Engineer', 'Software Engineer'],
    opportunity_types: ['internship', 'hackathon'],
    domains: ['Artificial Intelligence', 'Full Stack'],
    min_match_score: 0.6,
    auto_monitor_enabled: true,
    notifications_enabled: true,
    preferred_locations: [],
    remote_only: false,
    skills: [],
  });

  // Async indicators
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSavingPref, setIsSavingPref] = useState<boolean>(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Sync activeTab when activeTabDefault changes
  useEffect(() => {
    setActiveTab(activeTabDefault);
  }, [activeTabDefault]);

  // Set action notice helper
  const showNotice = (msg: string, duration: number = 3500) => {
    setActionNotice(msg);
    setTimeout(() => setActionNotice(null), duration);
  };

  // Load active tab data
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      if (activeTab === 'opportunities') {
        if (oppMode === 'catalog') {
          const opps = await voxaraService.getOpportunities(categoryFilter, 60);
          setOpportunities(opps);
        } else {
          // Personalized matches (requires auth)
          if (!user) {
            setErrorMessage('Sign in to view your personalized opportunity rankings and score breakdowns.');
            setMatchedOpportunities([]);
          } else {
            const res = await voxaraService.getMatchedOpportunities(
              categoryFilter !== 'all' ? categoryFilter : undefined
            );
            if (res.error) {
              setErrorMessage(res.error);
            } else {
              setMatchedOpportunities(res.opportunities);
            }
          }
        }
      } else if (activeTab === 'pipeline') {
        if (!user) {
          setErrorMessage('Sign in to access your personal application tracking pipeline.');
          setSavedOpportunities([]);
        } else {
          const res = await voxaraService.getSavedOpportunities(
            pipelineStatusFilter !== 'all' ? pipelineStatusFilter : undefined
          );
          if (res.error) {
            setErrorMessage(res.error);
          } else {
            setSavedOpportunities(res.data);
          }
        }
      } else if (activeTab === 'notifications') {
        if (!user) {
          setErrorMessage('Sign in to access your personal notification stream.');
          setNotifications([]);
        } else {
          const res = await voxaraService.getNotifications(notifUnreadOnly);
          if (res.error) {
            setErrorMessage(res.error);
          } else {
            setNotifications(res.data);
          }
        }
      } else if (activeTab === 'preferences') {
        if (!user) {
          setErrorMessage('Sign in to customize your career and opportunity match criteria.');
        } else {
          const res = await voxaraService.getPreferences();
          if (res.error) {
            setErrorMessage(res.error);
          } else if (res.data) {
            setPrefDraft(res.data);
          }
        }
      } else if (activeTab === 'telemetry') {
        const [execs, sched] = await Promise.all([
          voxaraService.getExecutions(),
          voxaraService.getSchedulerStatus(),
        ]);
        setExecutions(execs);
        setSchedulerStatus(sched);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to communicate with Voxara backend.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  }, [activeTab, oppMode, categoryFilter, user, pipelineStatusFilter, notifUnreadOnly]);

  // Initial and reactive load on open or tab switch
  useEffect(() => {
    if (isOpen) {
      void loadData();
    }
  }, [isOpen, loadData]);

  // Trigger manual discovery sweep via LangGraph
  const handleHuntNow = async () => {
    setIsLoading(true);
    showNotice('Hunting live opportunities across Devpost, Simplify & Arbeitnow...');
    try {
      const results = await voxaraService.huntOpportunities(
        searchQuery || 'all',
        categoryFilter !== 'all' ? categoryFilter : 'all'
      );
      setOpportunities(results);
      showNotice(`Discovered ${results.length} verified opportunities!`);
    } catch {
      setErrorMessage('Discovery sweep failed. Ensure backend server is running.');
    } finally {
      setIsLoading(false);
    }
  };

  // Save opportunity to user pipeline
  const handleSaveToPipeline = async (opp: OpportunityItem) => {
    if (!user) {
      showNotice('Please sign in to track opportunities in your personal pipeline.');
      return;
    }

    setIsLoading(true);
    const { data, error } = await voxaraService.saveOpportunity(
      opp.id,
      'saved',
      '',
      opp.match_score || 0.8
    );

    if (error) {
      showNotice(`Failed to save: ${error}`);
    } else if (data) {
      showNotice(`Tracked "${opp.title}" in your application pipeline!`);
      // Update local saved opportunities state
      setSavedOpportunities((prev) => [data, ...prev.filter((p) => p.id !== data.id)]);
    }
    setIsLoading(false);
  };

  // Update pipeline status
  const handleUpdatePipelineStatus = async (
    savedId: string,
    status: SavedOpportunityItem['status']
  ) => {
    const { data, error } = await voxaraService.updateSavedOpportunity(savedId, { status });
    if (error) {
      showNotice(`Update failed: ${error}`);
    } else if (data) {
      setSavedOpportunities((prev) =>
        prev.map((item) => (item.id === savedId ? { ...item, status } : item))
      );
      showNotice(`Status updated to "${status}".`);
    }
  };

  // Save notes on an opportunity
  const handleSaveNotes = async (savedId: string) => {
    const { data, error } = await voxaraService.updateSavedOpportunity(savedId, {
      notes: noteDraft,
    });
    if (error) {
      showNotice(`Failed to update notes: ${error}`);
    } else if (data) {
      setSavedOpportunities((prev) =>
        prev.map((item) => (item.id === savedId ? { ...item, notes: noteDraft } : item))
      );
      setEditingNoteId(null);
      showNotice('Notes saved successfully.');
    }
  };

  // Delete from pipeline
  const handleDeleteFromPipeline = async (savedId: string) => {
    const ok = await voxaraService.deleteSavedOpportunity(savedId);
    if (ok) {
      setSavedOpportunities((prev) => prev.filter((item) => item.id !== savedId));
      showNotice('Opportunity removed from pipeline.');
    } else {
      showNotice('Failed to remove opportunity.');
    }
  };

  // Mark single notification as read
  const handleMarkRead = async (notifId: string) => {
    const ok = await voxaraService.markNotificationRead(notifId);
    if (ok) {
      setNotifications((prev) =>
        prev.map((n) => (n.id === notifId ? { ...n, is_read: true } : n))
      );
    }
  };

  // Mark all notifications as read
  const handleMarkAllRead = async () => {
    const count = await voxaraService.markAllNotificationsRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    showNotice(`Marked ${count} notification(s) as read.`);
  };

  // Human confirmation gate
  const handleConfirm = async (notifId: string, token: string) => {
    setIsLoading(true);
    const ok = await voxaraService.confirmNotification(notifId, token);
    if (ok) {
      showNotice('Consequential action confirmed successfully!');
      const res = await voxaraService.getNotifications(notifUnreadOnly);
      if (res.data) setNotifications(res.data);
    } else {
      showNotice('Action confirmation failed or expired.');
    }
    setIsLoading(false);
  };

  // Save Preferences
  const handleSavePreferences = async () => {
    setIsSavingPref(true);
    const { data, error } = await voxaraService.updatePreferences(prefDraft);
    if (error) {
      showNotice(`Error saving preferences: ${error}`);
    } else if (data) {
      setPrefDraft(data);
      showNotice('Preferences saved! Matching engine updated.');
      // Pre-warm matches in background
      void voxaraService.getMatchedOpportunities();
    }
    setIsSavingPref(false);
  };

  // Check which opportunities are already saved in pipeline
  const savedOppIdSet = useMemo(() => {
    return new Set(savedOpportunities.map((s) => s.opportunity_id));
  }, [savedOpportunities]);

  // Filter displayed opportunities by search text
  const displayedOpps = useMemo(() => {
    const sourceList = oppMode === 'catalog' ? opportunities : matchedOpportunities;
    if (!searchQuery.trim()) return sourceList;
    const q = searchQuery.toLowerCase();
    return sourceList.filter(
      (opp) =>
        opp.title.toLowerCase().includes(q) ||
        opp.organization.toLowerCase().includes(q) ||
        opp.description?.toLowerCase().includes(q) ||
        opp.location?.toLowerCase().includes(q) ||
        opp.requirements?.some((r) => r.toLowerCase().includes(q))
    );
  }, [oppMode, opportunities, matchedOpportunities, searchQuery]);

  // Unread notifications count
  const unreadCount = useMemo(() => {
    return notifications.filter((n) => !n.is_read).length;
  }, [notifications]);

  if (!isOpen) return null;

  return (
    <aside
      aria-label="Agent Activity & Opportunity Panel"
      className="fixed inset-y-0 right-0 w-full sm:w-[480px] md:w-[520px] bg-[#FAF9F6]/95 backdrop-blur-2xl border-l border-neutral-300/80 shadow-2xl z-50 flex flex-col transition-all duration-300 animate-slideInRight"
    >
      {/* ----------------------------------------------------------------- */}
      {/* Top Header */}
      {/* ----------------------------------------------------------------- */}
      <div className="p-4 border-b border-neutral-200 flex items-center justify-between bg-white/80">
        <div className="flex items-center gap-2.5">
          <div className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse" />
          <div>
            <h2 className="text-sm font-bold text-neutral-900 tracking-tight flex items-center gap-1.5">
              <span>Voxara</span>
              <span className="text-amber-600 font-semibold">Opportunity Hub</span>
            </h2>
            <p className="text-[10px] text-neutral-400">Connected to FastAPI & Neon PostgreSQL</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void loadData()}
            disabled={isLoading}
            className="p-1.5 hover:bg-neutral-100 rounded-lg text-neutral-500 hover:text-neutral-900 transition-colors cursor-pointer disabled:opacity-50"
            title="Refresh active tab"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-amber-600' : ''}`} />
          </button>
          <button
            onClick={onClose}
            className="px-2 py-1 hover:bg-neutral-200/60 rounded-md text-neutral-500 hover:text-neutral-900 transition-colors cursor-pointer text-xs font-semibold"
          >
            Esc
          </button>
        </div>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* Navigation Tabs */}
      {/* ----------------------------------------------------------------- */}
      <div className="flex border-b border-neutral-200 text-xs font-medium bg-neutral-100/50 overflow-x-auto no-scrollbar">
        {/* Tab: Opportunities */}
        <button
          onClick={() => setActiveTab('opportunities')}
          className={`px-3.5 py-2.5 flex items-center gap-1.5 border-b-2 whitespace-nowrap transition-colors cursor-pointer ${
            activeTab === 'opportunities'
              ? 'border-amber-500 text-amber-900 font-semibold bg-white'
              : 'border-transparent text-neutral-500 hover:text-neutral-900'
          }`}
        >
          <Compass className="w-3.5 h-3.5 text-amber-600" />
          <span>Opportunities</span>
        </button>

        {/* Tab: Pipeline */}
        <button
          onClick={() => setActiveTab('pipeline')}
          className={`px-3.5 py-2.5 flex items-center gap-1.5 border-b-2 whitespace-nowrap transition-colors cursor-pointer ${
            activeTab === 'pipeline'
              ? 'border-blue-500 text-blue-900 font-semibold bg-white'
              : 'border-transparent text-neutral-500 hover:text-neutral-900'
          }`}
        >
          <BookmarkCheck className="w-3.5 h-3.5 text-blue-600" />
          <span>Pipeline</span>
          {savedOpportunities.length > 0 && (
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-blue-100 text-blue-800 font-bold">
              {savedOpportunities.length}
            </span>
          )}
        </button>

        {/* Tab: Alerts */}
        <button
          onClick={() => setActiveTab('notifications')}
          className={`px-3.5 py-2.5 flex items-center gap-1.5 border-b-2 whitespace-nowrap transition-colors cursor-pointer ${
            activeTab === 'notifications'
              ? 'border-purple-500 text-purple-900 font-semibold bg-white'
              : 'border-transparent text-neutral-500 hover:text-neutral-900'
          }`}
        >
          <Bell className="w-3.5 h-3.5 text-purple-600" />
          <span>Alerts</span>
          {unreadCount > 0 && (
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-red-100 text-red-700 font-bold animate-pulse">
              {unreadCount}
            </span>
          )}
        </button>

        {/* Tab: Preferences */}
        <button
          onClick={() => setActiveTab('preferences')}
          className={`px-3.5 py-2.5 flex items-center gap-1.5 border-b-2 whitespace-nowrap transition-colors cursor-pointer ${
            activeTab === 'preferences'
              ? 'border-amber-500 text-amber-900 font-semibold bg-white'
              : 'border-transparent text-neutral-500 hover:text-neutral-900'
          }`}
        >
          <Sliders className="w-3.5 h-3.5 text-amber-600" />
          <span>Criteria</span>
        </button>

        {/* Tab: Telemetry */}
        <button
          onClick={() => setActiveTab('telemetry')}
          className={`px-3.5 py-2.5 flex items-center gap-1.5 border-b-2 whitespace-nowrap transition-colors cursor-pointer ${
            activeTab === 'telemetry'
              ? 'border-emerald-500 text-emerald-900 font-semibold bg-white'
              : 'border-transparent text-neutral-500 hover:text-neutral-900'
          }`}
        >
          <Activity className="w-3.5 h-3.5 text-emerald-600" />
          <span>Telemetry</span>
        </button>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* Notice & Error Banners */}
      {/* ----------------------------------------------------------------- */}
      {actionNotice && (
        <div className="bg-amber-100/95 text-amber-950 text-xs px-4 py-2 border-b border-amber-200 flex items-center justify-between gap-2 animate-fadeIn">
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-amber-600 shrink-0" />
            <span className="font-medium">{actionNotice}</span>
          </div>
          <button onClick={() => setActionNotice(null)} className="text-amber-700 hover:text-amber-950">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="bg-red-50 text-red-900 text-xs px-4 py-2.5 border-b border-red-200 flex items-center justify-between gap-2 animate-fadeIn">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => void loadData()}
            className="text-xs font-semibold text-red-700 underline cursor-pointer hover:text-red-900 shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* Content Area */}
      {/* ----------------------------------------------------------------- */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
        {/* =============================================================== */}
        {/* TAB 1: OPPORTUNITIES (CATALOG & PERSONALIZED MATCHES)             */}
        {/* =============================================================== */}
        {activeTab === 'opportunities' && (
          <div className="space-y-3">
            {/* View Mode Toggle: All Discovered vs My Personalized Matches */}
            <div className="flex items-center justify-between gap-2 bg-neutral-200/50 p-1 rounded-xl">
              <button
                onClick={() => setOppMode('catalog')}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                  oppMode === 'catalog'
                    ? 'bg-white text-neutral-900 shadow-2xs'
                    : 'text-neutral-500 hover:text-neutral-900'
                }`}
              >
                All Discovered ({opportunities.length})
              </button>
              <button
                onClick={() => setOppMode('matches')}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                  oppMode === 'matches'
                    ? 'bg-white text-amber-900 shadow-2xs font-bold'
                    : 'text-neutral-500 hover:text-neutral-900'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                <span>My Matches ({matchedOpportunities.length})</span>
              </button>
            </div>

            {/* Search Input Bar & Live Discovery Button */}
            <div className="flex items-center gap-2">
              <div className="flex-1 relative">
                <Search className="w-3.5 h-3.5 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter by title, company, skills..."
                  className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-neutral-300 rounded-lg focus:outline-hidden focus:border-amber-500"
                />
              </div>
              <button
                onClick={handleHuntNow}
                disabled={isLoading}
                title="Trigger real-time opportunity discovery across sources"
                className="px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-semibold shadow-2xs transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shrink-0"
              >
                <Compass className="w-3.5 h-3.5" />
                <span>Hunt</span>
              </button>
            </div>

            {/* Category Filter Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
              <span className="text-[11px] text-neutral-400 font-medium">Category:</span>
              {['all', 'internship', 'hackathon', 'fellowship'].map((cat) => (
                <button
                  key={cat}
                  onClick={() => setCategoryFilter(cat)}
                  className={`px-2.5 py-1 rounded-full text-[11px] font-medium capitalize cursor-pointer transition-all ${
                    categoryFilter === cat
                      ? 'bg-amber-100 text-amber-900 font-semibold border border-amber-300'
                      : 'bg-white border border-neutral-200 text-neutral-600 hover:border-neutral-300'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Opportunities List */}
            {isLoading && displayedOpps.length === 0 ? (
              <div className="p-12 text-center text-neutral-400 text-xs space-y-2">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto text-amber-500" />
                <p>Loading real opportunities from backend...</p>
              </div>
            ) : displayedOpps.length === 0 ? (
              <div className="p-8 text-center text-neutral-400 text-xs border border-dashed rounded-xl border-neutral-300 space-y-2">
                <p className="font-medium text-neutral-600">No opportunities match your filter.</p>
                <p className="text-[11px]">Click "Hunt" to discover fresh openings across Devpost, Simplify, and Arbeitnow.</p>
              </div>
            ) : (
              displayedOpps.map((opp) => {
                const isTracked = savedOppIdSet.has(opp.id);
                return (
                  <article
                    key={opp.id}
                    className="p-3.5 bg-white border border-neutral-200/90 rounded-xl space-y-2 hover:border-amber-400/80 transition-all shadow-2xs"
                  >
                    {/* Header Row */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-1.5">
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-900 uppercase">
                            {opp.type}
                          </span>
                          {opp.verified_status === 'verified' && (
                            <span className="flex items-center gap-0.5 text-[10px] font-medium text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200/60">
                              <ShieldCheck className="w-3 h-3 text-emerald-600" />
                              Verified
                            </span>
                          )}
                        </div>
                        <h4 className="text-sm font-bold text-neutral-900 leading-snug">{opp.title}</h4>
                        <p className="text-xs text-neutral-600 font-medium">{opp.organization}</p>
                      </div>

                      {/* Match Score Badge */}
                      {opp.match_score !== undefined && opp.match_score > 0 && (
                        <div className="text-right shrink-0">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
                              opp.match_score >= 0.8
                                ? 'bg-emerald-100 text-emerald-900 border border-emerald-300'
                                : opp.match_score >= 0.6
                                ? 'bg-amber-100 text-amber-900 border border-amber-300'
                                : 'bg-neutral-100 text-neutral-700'
                            }`}
                          >
                            {Math.round(opp.match_score * 100)}% match
                          </span>
                          {opp.relevance_tier && (
                            <p className="text-[10px] text-neutral-400 font-medium mt-0.5">
                              {opp.relevance_tier}
                            </p>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Match Explanation (Personalized matching mode) */}
                    {opp.match_explanation && (
                      <div className="text-[11px] text-amber-950 bg-amber-50/70 p-2 rounded-lg border border-amber-200/60 leading-relaxed">
                        <span className="font-semibold text-amber-900">Why matched: </span>
                        {opp.match_explanation}
                      </div>
                    )}

                    {/* Description */}
                    {opp.description && (
                      <p className="text-xs text-neutral-600 leading-relaxed line-clamp-3">
                        {opp.description}
                      </p>
                    )}

                    {/* Metadata tags: Location & Deadline */}
                    <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-neutral-500">
                      {opp.location && (
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-neutral-400" />
                          <span>{opp.location}</span>
                        </span>
                      )}
                      {opp.deadline && (
                        <span className="flex items-center gap-1 text-red-700 font-medium bg-red-50/80 px-1.5 py-0.5 rounded">
                          <Clock className="w-3 h-3 text-red-500" />
                          <span>Due {new Date(opp.deadline).toLocaleDateString()}</span>
                        </span>
                      )}
                      <span className="text-neutral-400">Source: {opp.source_name}</span>
                    </div>

                    {/* Action buttons */}
                    <div className="pt-2 border-t border-neutral-100 flex items-center justify-between text-xs">
                      {isTracked ? (
                        <span className="flex items-center gap-1 text-emerald-700 font-semibold text-[11px]">
                          <Check className="w-3.5 h-3.5" />
                          <span>In Pipeline</span>
                        </span>
                      ) : (
                        <button
                          onClick={() => void handleSaveToPipeline(opp)}
                          disabled={isLoading}
                          className="flex items-center gap-1 text-blue-700 hover:text-blue-900 font-semibold bg-blue-50 hover:bg-blue-100 px-2.5 py-1 rounded-md border border-blue-200 transition-colors cursor-pointer disabled:opacity-50"
                        >
                          <Plus className="w-3 h-3" />
                          <span>Track Application</span>
                        </button>
                      )}

                      <a
                        href={opp.application_url || opp.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-amber-700 hover:text-amber-900 font-semibold bg-amber-50 hover:bg-amber-100 px-2.5 py-1 rounded-md border border-amber-200 transition-colors"
                      >
                        <span>Apply</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </article>
                );
              })
            )}
          </div>
        )}

        {/* =============================================================== */}
        {/* TAB 2: MY PIPELINE (APPLICATION TRACKING)                        */}
        {/* =============================================================== */}
        {activeTab === 'pipeline' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1">
              <div>
                <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider">
                  Application Tracking Pipeline
                </h3>
                <p className="text-[11px] text-neutral-500">Live statuses and personal application notes</p>
              </div>
            </div>

            {/* Status Filter Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
              {['all', 'saved', 'applied', 'interviewing', 'offered', 'rejected'].map((st) => (
                <button
                  key={st}
                  onClick={() => setPipelineStatusFilter(st)}
                  className={`px-2.5 py-1 rounded-full text-[11px] font-medium capitalize cursor-pointer transition-all ${
                    pipelineStatusFilter === st
                      ? 'bg-blue-100 text-blue-900 font-semibold border border-blue-300'
                      : 'bg-white border border-neutral-200 text-neutral-600 hover:border-neutral-300'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>

            {savedOpportunities.length === 0 ? (
              <div className="p-8 text-center text-neutral-400 text-xs border border-dashed rounded-xl border-neutral-300 space-y-2">
                <p className="font-medium text-neutral-600">Your application pipeline is empty.</p>
                <p className="text-[11px]">
                  Browse opportunities and tap <span className="font-semibold text-blue-700">"Track Application"</span> to begin tracking deadlines and interview progress.
                </p>
              </div>
            ) : (
              savedOpportunities.map((item) => (
                <article
                  key={item.id}
                  className="p-3.5 bg-white border border-neutral-200 rounded-xl space-y-2.5 hover:border-blue-400/80 transition-all shadow-2xs"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-sm font-bold text-neutral-900 leading-snug">
                        {item.opportunity?.title || 'Tracked Application'}
                      </h4>
                      <p className="text-xs text-neutral-500 font-medium">
                        {item.opportunity?.organization || 'Organization'}
                      </p>
                    </div>
                    <button
                      onClick={() => void handleDeleteFromPipeline(item.id)}
                      className="p-1 text-neutral-400 hover:text-red-600 transition-colors cursor-pointer"
                      title="Remove from pipeline"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* Deadline info */}
                  {item.opportunity?.deadline && (
                    <div className="flex items-center gap-1.5 text-xs text-red-700 bg-red-50/80 px-2 py-1 rounded border border-red-200/50">
                      <Clock className="w-3 h-3 text-red-500 shrink-0" />
                      <span className="font-medium">
                        Deadline: {new Date(item.opportunity.deadline).toLocaleDateString()}
                      </span>
                    </div>
                  )}

                  {/* Notes Section with Inline Edit */}
                  <div className="space-y-1">
                    {editingNoteId === item.id ? (
                      <div className="space-y-1.5">
                        <textarea
                          value={noteDraft}
                          onChange={(e) => setNoteDraft(e.target.value)}
                          placeholder="Add personal interview dates, contact notes, referral info..."
                          className="w-full p-2 text-xs bg-neutral-50 border border-neutral-300 rounded-lg focus:outline-hidden focus:border-blue-500"
                          rows={2}
                        />
                        <div className="flex items-center gap-2 justify-end">
                          <button
                            onClick={() => setEditingNoteId(null)}
                            className="text-[11px] text-neutral-500 hover:text-neutral-700 px-2 py-0.5"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={() => void handleSaveNotes(item.id)}
                            className="flex items-center gap-1 text-[11px] font-semibold bg-blue-600 hover:bg-blue-700 text-white px-2.5 py-1 rounded cursor-pointer"
                          >
                            <Save className="w-3 h-3" />
                            <span>Save Note</span>
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start justify-between gap-2 bg-neutral-50 p-2 rounded-lg border border-neutral-200/70 text-xs text-neutral-700">
                        <p className="flex-1 leading-relaxed">
                          {item.notes ? item.notes : <span className="text-neutral-400 italic">No notes yet.</span>}
                        </p>
                        <button
                          onClick={() => {
                            setEditingNoteId(item.id);
                            setNoteDraft(item.notes || '');
                          }}
                          className="p-1 text-neutral-400 hover:text-blue-600 transition-colors"
                          title="Edit application note"
                        >
                          <FileEdit className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Footer: Status Selector & Direct Application Link */}
                  <div className="pt-2 border-t border-neutral-100 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[11px] text-neutral-400 font-semibold uppercase">Status:</span>
                      <select
                        value={item.status}
                        onChange={(e) =>
                          void handleUpdatePipelineStatus(
                            item.id,
                            e.target.value as SavedOpportunityItem['status']
                          )
                        }
                        className="text-xs font-semibold px-2 py-0.5 rounded border border-neutral-300 bg-white text-neutral-800 cursor-pointer focus:outline-hidden"
                      >
                        <option value="saved">Saved</option>
                        <option value="applied">Applied</option>
                        <option value="interviewing">Interviewing</option>
                        <option value="offered">Offered 🎉</option>
                        <option value="rejected">Rejected</option>
                        <option value="archived">Archived</option>
                      </select>
                    </div>

                    {item.opportunity && (
                      <a
                        href={item.opportunity.application_url || item.opportunity.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-blue-700 hover:text-blue-900 font-medium"
                      >
                        <span>View Portal</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                </article>
              ))
            )}
          </div>
        )}

        {/* =============================================================== */}
        {/* TAB 3: NOTIFICATIONS & CONFIRMATION GATES                        */}
        {/* =============================================================== */}
        {activeTab === 'notifications' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1">
              <div>
                <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider">
                  Persistent Alerts & Approaching Deadlines
                </h3>
                <p className="text-[11px] text-neutral-500">Autonomous notifications stored in Neon PostgreSQL</p>
              </div>

              {notifications.length > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="flex items-center gap-1 text-[11px] text-purple-700 hover:text-purple-900 font-semibold bg-purple-50 hover:bg-purple-100 px-2 py-1 rounded border border-purple-200 cursor-pointer"
                >
                  <CheckCheck className="w-3 h-3" />
                  <span>Mark All Read</span>
                </button>
              )}
            </div>

            {/* Filter Toggle: All vs Unread */}
            <div className="flex items-center gap-2 text-xs">
              <button
                onClick={() => setNotifUnreadOnly(false)}
                className={`px-2.5 py-1 rounded-full text-[11px] font-medium cursor-pointer ${
                  !notifUnreadOnly
                    ? 'bg-purple-100 text-purple-900 font-semibold border border-purple-300'
                    : 'bg-white border border-neutral-200 text-neutral-600'
                }`}
              >
                All Alerts ({notifications.length})
              </button>
              <button
                onClick={() => setNotifUnreadOnly(true)}
                className={`px-2.5 py-1 rounded-full text-[11px] font-medium cursor-pointer ${
                  notifUnreadOnly
                    ? 'bg-purple-100 text-purple-900 font-semibold border border-purple-300'
                    : 'bg-white border border-neutral-200 text-neutral-600'
                }`}
              >
                Unread ({unreadCount})
              </button>
            </div>

            {notifications.length === 0 ? (
              <div className="p-8 text-center text-neutral-400 text-xs border border-dashed rounded-xl border-neutral-300 space-y-1">
                <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto mb-1" />
                <p className="font-medium text-neutral-700">All caught up!</p>
                <p className="text-[11px]">Zero pending alerts or approaching deadline notifications.</p>
              </div>
            ) : (
              notifications.map((notif) => (
                <div
                  key={notif.id}
                  className={`p-3.5 rounded-xl border space-y-2 text-xs transition-all shadow-2xs ${
                    !notif.is_read
                      ? 'bg-white border-purple-200/90 ring-1 ring-purple-100'
                      : 'bg-neutral-50/80 border-neutral-200 text-neutral-600'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-1.5 font-bold text-neutral-900">
                      {notif.type === 'deadline' ? (
                        <Clock className="w-3.5 h-3.5 text-red-600 shrink-0" />
                      ) : notif.requires_confirmation ? (
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                      ) : (
                        <Bell className="w-3.5 h-3.5 text-purple-600 shrink-0" />
                      )}
                      <span className={notif.is_read ? 'font-medium text-neutral-800' : 'font-bold'}>
                        {notif.title}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <span
                        className={`text-[9px] uppercase px-1.5 py-0.2 rounded font-bold ${
                          notif.priority === 'urgent'
                            ? 'bg-red-100 text-red-800'
                            : notif.priority === 'high'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-neutral-100 text-neutral-600'
                        }`}
                      >
                        {notif.priority}
                      </span>
                      {!notif.is_read && (
                        <button
                          onClick={() => void handleMarkRead(notif.id)}
                          title="Mark as read"
                          className="text-neutral-400 hover:text-purple-700 p-0.5 cursor-pointer"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>

                  <p className="text-neutral-700 leading-relaxed text-xs">{notif.message}</p>

                  <div className="flex items-center justify-between pt-1 text-[10px] text-neutral-400">
                    <span>
                      {notif.created_at ? new Date(notif.created_at).toLocaleString() : 'Recent'}
                    </span>
                    {notif.is_read && <span className="text-emerald-600 font-medium">Read</span>}
                  </div>

                  {/* Human Confirmation Gate */}
                  {notif.requires_confirmation && notif.confirmation_token && (
                    <div className="pt-2 border-t border-amber-200/70 flex items-center justify-between">
                      <span className="text-[11px] text-amber-900 font-medium flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3 text-amber-600" />
                        Confirmation Gate
                      </span>
                      <button
                        onClick={() => void handleConfirm(notif.id, notif.confirmation_token!)}
                        className="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                      >
                        Confirm Action
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* =============================================================== */}
        {/* TAB 4: USER MATCH PREFERENCES & CRITERIA                        */}
        {/* =============================================================== */}
        {activeTab === 'preferences' && (
          <div className="space-y-4">
            <div>
              <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider">
                Career & Opportunity Preferences
              </h3>
              <p className="text-[11px] text-neutral-500">
                Powers rule-based matching scores and autonomous deadline alerts
              </p>
            </div>

            {/* Target Job Roles */}
            <div className="space-y-1.5 bg-white p-3.5 rounded-xl border border-neutral-200 shadow-2xs">
              <label className="text-xs font-bold text-neutral-900">Target Roles</label>
              <p className="text-[11px] text-neutral-500">Select roles to prioritize in matches:</p>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {['AI Engineer', 'Software Engineer', 'Full Stack', 'Machine Learning', 'Systems Engineer', 'Frontend'].map(
                  (role) => {
                    const active = prefDraft.roles.includes(role);
                    return (
                      <button
                        key={role}
                        onClick={() => {
                          const updated = active
                            ? prefDraft.roles.filter((r) => r !== role)
                            : [...prefDraft.roles, role];
                          setPrefDraft({ ...prefDraft, roles: updated });
                        }}
                        className={`px-2.5 py-1 rounded-full text-xs font-medium cursor-pointer transition-all ${
                          active
                            ? 'bg-amber-100 text-amber-900 font-semibold border border-amber-300'
                            : 'bg-neutral-50 border border-neutral-200 text-neutral-600 hover:border-neutral-300'
                        }`}
                      >
                        {role} {active && '✓'}
                      </button>
                    );
                  }
                )}
              </div>
            </div>

            {/* Preferred Opportunity Types */}
            <div className="space-y-1.5 bg-white p-3.5 rounded-xl border border-neutral-200 shadow-2xs">
              <label className="text-xs font-bold text-neutral-900">Opportunity Categories</label>
              <div className="grid grid-cols-3 gap-2 pt-1 text-xs">
                {['internship', 'hackathon', 'fellowship'].map((type) => {
                  const active = prefDraft.opportunity_types.includes(type);
                  return (
                    <button
                      key={type}
                      onClick={() => {
                        const updated = active
                          ? prefDraft.opportunity_types.filter((t) => t !== type)
                          : [...prefDraft.opportunity_types, type];
                        setPrefDraft({ ...prefDraft, opportunity_types: updated });
                      }}
                      className={`p-2 rounded-lg text-center font-medium capitalize cursor-pointer transition-all border ${
                        active
                          ? 'bg-amber-50 border-amber-400 text-amber-900 font-bold'
                          : 'bg-neutral-50 border-neutral-200 text-neutral-600 hover:border-neutral-300'
                      }`}
                    >
                      {type}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Minimum Match Score Slider */}
            <div className="space-y-1.5 bg-white p-3.5 rounded-xl border border-neutral-200 shadow-2xs">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-neutral-900">Minimum Match Score Threshold</label>
                <span className="text-xs font-bold text-amber-600">
                  {Math.round(prefDraft.min_match_score * 100)}%
                </span>
              </div>
              <input
                type="range"
                min="0.3"
                max="0.9"
                step="0.05"
                value={prefDraft.min_match_score}
                onChange={(e) =>
                  setPrefDraft({ ...prefDraft, min_match_score: parseFloat(e.target.value) })
                }
                className="w-full accent-amber-500 cursor-pointer"
              />
              <p className="text-[10px] text-neutral-400">
                Opportunities scoring below this threshold are omitted from your "My Matches" feed.
              </p>
            </div>

            {/* Toggles: Remote Only & Autonomous Notifications */}
            <div className="space-y-2 bg-white p-3.5 rounded-xl border border-neutral-200 shadow-2xs text-xs">
              <label className="flex items-center justify-between cursor-pointer">
                <span className="font-bold text-neutral-800">Remote Opportunities Only</span>
                <input
                  type="checkbox"
                  checked={prefDraft.remote_only}
                  onChange={(e) => setPrefDraft({ ...prefDraft, remote_only: e.target.checked })}
                  className="w-4 h-4 accent-amber-500 rounded cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer pt-2 border-t border-neutral-100">
                <div>
                  <span className="font-bold text-neutral-800">Autonomous Alerts & Deadlines</span>
                  <p className="text-[10px] text-neutral-400">Receive persistent alerts when deadlines approach.</p>
                </div>
                <input
                  type="checkbox"
                  checked={prefDraft.notifications_enabled}
                  onChange={(e) =>
                    setPrefDraft({ ...prefDraft, notifications_enabled: e.target.checked })
                  }
                  className="w-4 h-4 accent-amber-500 rounded cursor-pointer"
                />
              </label>
            </div>

            {/* Save Button */}
            <button
              onClick={handleSavePreferences}
              disabled={isSavingPref}
              className="w-full py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-xs font-bold shadow-xs transition-colors flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              <span>{isSavingPref ? 'Saving Criteria...' : 'Save Match Criteria'}</span>
            </button>
          </div>
        )}

        {/* =============================================================== */}
        {/* TAB 5: TELEMETRY & SCHEDULER                                     */}
        {/* =============================================================== */}
        {activeTab === 'telemetry' && (
          <div className="space-y-3">
            <div>
              <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider">
                LangGraph Telemetry & Scheduler Health
              </h3>
              <p className="text-[11px] text-neutral-500">Autonomous Execution Telemetry in PostgreSQL</p>
            </div>

            {/* Scheduler Status Card */}
            {schedulerStatus && (
              <div className="p-3 bg-amber-50/60 border border-amber-200 rounded-xl space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-amber-950 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-amber-600" />
                    Scheduled Opportunity Engine
                  </span>
                  <span
                    className={`px-2 py-0.2 rounded-full text-[10px] font-bold ${
                      schedulerStatus.is_running
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-neutral-200 text-neutral-700'
                    }`}
                  >
                    {schedulerStatus.is_running ? 'Active (Running)' : 'Standalone Worker Mode'}
                  </span>
                </div>
                <div className="text-[11px] text-neutral-600 space-y-0.5">
                  <p>Sweep interval: <span className="font-semibold text-neutral-800">{schedulerStatus.interval_minutes} minutes</span></p>
                  <p>Batch size: <span className="font-semibold text-neutral-800">{schedulerStatus.batch_size} opportunities</span></p>
                  <p>Deadline alert window: <span className="font-semibold text-neutral-800">{schedulerStatus.deadline_alert_days} days</span></p>
                </div>
              </div>
            )}

            {/* Workflow Executions List */}
            {executions.length === 0 ? (
              <div className="p-8 text-center text-neutral-400 text-xs border border-dashed rounded-xl border-neutral-300">
                No workflow telemetry recorded yet.
              </div>
            ) : (
              executions.map((exec) => (
                <div
                  key={exec.execution_id}
                  className="p-3 bg-white border border-neutral-200 rounded-xl space-y-2 text-xs shadow-2xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] font-semibold text-neutral-700">
                      {exec.execution_id}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        exec.status === 'completed' || exec.status === 'success'
                          ? 'bg-emerald-100 text-emerald-800'
                          : exec.status === 'failed'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {exec.status}
                    </span>
                  </div>

                  {exec.task && <p className="text-neutral-700 font-medium">{exec.task}</p>}

                  {exec.events && exec.events.length > 0 && (
                    <div className="space-y-1 pt-1">
                      <p className="text-[10px] text-neutral-400 font-semibold uppercase">Node Execution Sequence</p>
                      {exec.events.map((evt, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between text-[11px] bg-neutral-50 p-1.5 rounded border border-neutral-200/60"
                        >
                          <div className="flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            <span className="font-medium text-neutral-800">{evt.node_name}</span>
                          </div>
                          <div className="flex items-center gap-2 text-neutral-500 font-mono text-[10px]">
                            <span>{evt.status}</span>
                            {evt.duration_ms !== null && evt.duration_ms !== undefined && (
                              <span className="text-neutral-400">({evt.duration_ms}ms)</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
