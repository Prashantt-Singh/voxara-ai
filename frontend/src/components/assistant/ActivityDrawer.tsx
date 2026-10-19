import React, { useState, useEffect } from 'react';
import { voxaraService } from '../../lib/voxaraService';
import type {
  OpportunityItem,
  SavedOpportunityItem,
  NotificationItem,
  ExecutionRecord,
} from '../../lib/voxaraService';
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
} from 'lucide-react';

interface ActivityDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  activeTabDefault?: 'opportunities' | 'pipeline' | 'telemetry' | 'notifications';
}

export const ActivityDrawer: React.FC<ActivityDrawerProps> = ({
  isOpen,
  onClose,
  activeTabDefault = 'opportunities',
}) => {
  const [activeTab, setActiveTab] = useState<'opportunities' | 'pipeline' | 'telemetry' | 'notifications'>(
    activeTabDefault
  );

  const [opportunities, setOpportunities] = useState<OpportunityItem[]>([]);
  const [savedOpportunities, setSavedOpportunities] = useState<SavedOpportunityItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [executions, setExecutions] = useState<ExecutionRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Sync activeTab when activeTabDefault changes
  useEffect(() => {
    setActiveTab(activeTabDefault);
  }, [activeTabDefault]);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [opps, saved, notifs, execs] = await Promise.all([
        voxaraService.getOpportunities(),
        voxaraService.getSavedOpportunities(),
        voxaraService.getNotifications(),
        voxaraService.getExecutions(),
      ]);
      setOpportunities(opps);
      setSavedOpportunities(saved);
      setNotifications(notifs);
      setExecutions(execs);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      void loadData();
    }
  }, [isOpen]);

  const handleHuntNow = async () => {
    setIsLoading(true);
    setActionNotice('Hunting for new verified opportunities...');
    const results = await voxaraService.huntOpportunities('all', 'all');
    setOpportunities(results);
    const execs = await voxaraService.getExecutions();
    setExecutions(execs);
    setIsLoading(false);
    setActionNotice(`Discovered ${results.length} opportunities!`);
    setTimeout(() => setActionNotice(null), 4000);
  };

  const handleSaveToPipeline = async (opp: OpportunityItem) => {
    setIsLoading(true);
    const saved = await voxaraService.saveOpportunity(opp.id, 'saved', '', opp.match_score || 0.8);
    if (saved) {
      const updatedList = await voxaraService.getSavedOpportunities();
      setSavedOpportunities(updatedList);
      setActionNotice(`Saved "${opp.title}" to your application pipeline!`);
    } else {
      setActionNotice(`Failed to save "${opp.title}".`);
    }
    setIsLoading(false);
    setTimeout(() => setActionNotice(null), 3500);
  };

  const handleUpdatePipelineStatus = async (
    savedId: string,
    status: 'saved' | 'applied' | 'interviewing' | 'offered' | 'rejected' | 'archived'
  ) => {
    const updated = await voxaraService.updateSavedOpportunity(savedId, { status });
    if (updated) {
      setSavedOpportunities((prev) =>
        prev.map((item) => (item.id === savedId ? { ...item, status } : item))
      );
      setActionNotice(`Application status updated to "${status}".`);
      setTimeout(() => setActionNotice(null), 3000);
    }
  };

  const handleDeleteFromPipeline = async (savedId: string) => {
    const ok = await voxaraService.deleteSavedOpportunity(savedId);
    if (ok) {
      setSavedOpportunities((prev) => prev.filter((item) => item.id !== savedId));
      setActionNotice('Removed opportunity from your pipeline.');
      setTimeout(() => setActionNotice(null), 3000);
    }
  };

  const handleConfirm = async (notifId: string, token: string) => {
    setIsLoading(true);
    const ok = await voxaraService.confirmNotification(notifId, token);
    if (ok) {
      setActionNotice('Consequential action confirmed and verified!');
      const notifs = await voxaraService.getNotifications();
      setNotifications(notifs);
    } else {
      setActionNotice('Action confirmation failed. Please check credentials.');
    }
    setIsLoading(false);
    setTimeout(() => setActionNotice(null), 4000);
  };

  if (!isOpen) return null;

  return (
    <aside
      aria-label="Agent Activity & Opportunity Panel"
      className="fixed inset-y-0 right-0 w-full sm:w-115 bg-white/95 backdrop-blur-xl border-l border-neutral-200 shadow-2xl z-50 flex flex-col transition-all duration-300 animate-slideInRight"
    >
      {/* Top Header */}
      <div className="p-4 border-b border-neutral-200 flex items-center justify-between bg-neutral-50/80">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <h2 className="text-sm font-bold text-neutral-900 tracking-wide">
            Voxara AI Opportunity Engine
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void loadData()}
            disabled={isLoading}
            className="p-1.5 hover:bg-neutral-200 rounded-lg text-neutral-500 hover:text-neutral-800 transition-colors cursor-pointer disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-neutral-200 rounded-lg text-neutral-500 hover:text-neutral-800 transition-colors cursor-pointer text-xs font-semibold px-2.5"
          >
            Esc
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-neutral-200 text-xs font-medium bg-neutral-50/50">
        <button
          onClick={() => setActiveTab('opportunities')}
          className={`flex-1 py-2.5 flex items-center justify-center gap-1.5 border-b-2 transition-colors cursor-pointer ${
            activeTab === 'opportunities'
              ? 'border-amber-500 text-amber-900 font-semibold bg-amber-50/30'
              : 'border-transparent text-neutral-500 hover:text-neutral-900'
          }`}
        >
          <Compass className="w-3.5 h-3.5 text-amber-600" />
          <span>Opportunities</span>
          {opportunities.length > 0 && (
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-amber-100 text-amber-800">
              {opportunities.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('pipeline')}
          className={`flex-1 py-2.5 flex items-center justify-center gap-1.5 border-b-2 transition-colors cursor-pointer ${
            activeTab === 'pipeline'
              ? 'border-blue-500 text-blue-900 font-semibold bg-blue-50/30'
              : 'border-transparent text-neutral-500 hover:text-neutral-900'
          }`}
        >
          <BookmarkCheck className="w-3.5 h-3.5 text-blue-600" />
          <span>My Pipeline</span>
          {savedOpportunities.length > 0 && (
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-blue-100 text-blue-800">
              {savedOpportunities.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('telemetry')}
          className={`flex-1 py-2.5 flex items-center justify-center gap-1.5 border-b-2 transition-colors cursor-pointer ${
            activeTab === 'telemetry'
              ? 'border-emerald-500 text-emerald-900 font-semibold bg-emerald-50/30'
              : 'border-transparent text-neutral-500 hover:text-neutral-900'
          }`}
        >
          <Activity className="w-3.5 h-3.5 text-emerald-600" />
          <span>Telemetry</span>
        </button>

        <button
          onClick={() => setActiveTab('notifications')}
          className={`flex-1 py-2.5 flex items-center justify-center gap-1.5 border-b-2 transition-colors cursor-pointer ${
            activeTab === 'notifications'
              ? 'border-purple-500 text-purple-900 font-semibold bg-purple-50/30'
              : 'border-transparent text-neutral-500 hover:text-neutral-900'
          }`}
        >
          <Bell className="w-3.5 h-3.5 text-purple-600" />
          <span>Alerts</span>
          {notifications.length > 0 && (
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-red-100 text-red-700 font-bold">
              {notifications.length}
            </span>
          )}
        </button>
      </div>

      {/* Action Notice Banner */}
      {actionNotice && (
        <div className="bg-amber-100/90 text-amber-900 text-xs px-4 py-2 border-b border-amber-200 flex items-center gap-2 animate-fadeIn">
          <Sparkles className="w-3.5 h-3.5 text-amber-600 shrink-0" />
          <span className="font-medium">{actionNotice}</span>
        </div>
      )}

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* TAB 1: OPPORTUNITIES (SHARED CATALOG) */}
        {activeTab === 'opportunities' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1">
              <div>
                <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider">
                  Opportunity Hunter
                </h3>
                <p className="text-[11px] text-neutral-500">Live Hackathons, Fellowships & Internships</p>
              </div>
              <button
                onClick={handleHuntNow}
                disabled={isLoading}
                className="px-3 py-1 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-medium shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <Compass className="w-3 h-3" />
                <span>Hunt Now</span>
              </button>
            </div>

            {opportunities.length === 0 ? (
              <div className="p-8 text-center text-neutral-400 text-xs border border-dashed rounded-xl border-neutral-300">
                No opportunities saved yet. Tap "Hunt Now" or speak aloud to Voxara!
              </div>
            ) : (
              opportunities.map((opp) => (
                <article
                  key={opp.id}
                  className="p-3.5 bg-neutral-50 border border-neutral-200 rounded-xl space-y-2 hover:border-amber-300 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="inline-block px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800 uppercase">
                        {opp.type}
                      </span>
                      <h4 className="text-sm font-bold text-neutral-900 mt-1 leading-snug">{opp.title}</h4>
                      <p className="text-xs text-neutral-600 font-medium">{opp.organization}</p>
                    </div>
                    {opp.match_score && opp.match_score > 0 && (
                      <span className="shrink-0 px-2 py-1 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">
                        {Math.round(opp.match_score * 100)}% match
                      </span>
                    )}
                  </div>

                  <p className="text-xs text-neutral-600 leading-relaxed">{opp.description}</p>

                  {opp.deadline && (
                    <div className="flex items-center gap-1.5 text-xs text-red-700 bg-red-50 px-2 py-1 rounded">
                      <Clock className="w-3 h-3 shrink-0" />
                      <span className="font-medium">Deadline: {new Date(opp.deadline).toLocaleDateString()}</span>
                    </div>
                  )}

                  <div className="pt-1 flex items-center justify-between text-xs">
                    <span className="text-[11px] text-neutral-400">Source: {opp.source_name}</span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => void handleSaveToPipeline(opp)}
                        disabled={isLoading}
                        className="flex items-center gap-1 text-blue-700 hover:text-blue-800 font-medium bg-blue-50 px-2 py-0.5 rounded border border-blue-200/80 cursor-pointer disabled:opacity-50"
                      >
                        <Plus className="w-3 h-3" />
                        <span>Track</span>
                      </button>
                      <a
                        href={opp.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-amber-700 hover:text-amber-800 font-medium"
                      >
                        <span>Apply</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                </article>
              ))
            )}
          </div>
        )}

        {/* TAB 2: MY PIPELINE (USER SAVED OPPORTUNITIES) */}
        {activeTab === 'pipeline' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1">
              <div>
                <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider">
                  My Applications & Pipeline
                </h3>
                <p className="text-[11px] text-neutral-500">Track deadlines, interview status, and personal notes</p>
              </div>
            </div>

            {savedOpportunities.length === 0 ? (
              <div className="p-8 text-center text-neutral-400 text-xs border border-dashed rounded-xl border-neutral-300">
                Your application pipeline is empty. Browse "Opportunities" and click "Track" to add internships or hackathons!
              </div>
            ) : (
              savedOpportunities.map((item) => (
                <article
                  key={item.id}
                  className="p-3.5 bg-neutral-50 border border-neutral-200 rounded-xl space-y-2 hover:border-blue-300 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-sm font-bold text-neutral-900 leading-snug">
                        {item.opportunity?.title || 'Tracked Opportunity'}
                      </h4>
                      <p className="text-xs text-neutral-500 font-medium">
                        {item.opportunity?.organization || 'Devpost / Company'}
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

                  {item.notes && (
                    <p className="text-xs text-neutral-600 bg-white p-2 rounded border border-neutral-200/80">
                      📝 {item.notes}
                    </p>
                  )}

                  {item.opportunity?.deadline && (
                    <div className="flex items-center gap-1.5 text-xs text-red-700 bg-red-50 px-2 py-1 rounded">
                      <Clock className="w-3 h-3 shrink-0" />
                      <span className="font-medium">
                        Deadline: {new Date(item.opportunity.deadline).toLocaleDateString()}
                      </span>
                    </div>
                  )}

                  <div className="pt-2 border-t border-neutral-200 flex items-center justify-between text-xs">
                    <span className="text-[11px] text-neutral-400 font-semibold uppercase">Status:</span>
                    <select
                      value={item.status}
                      onChange={(e) =>
                        void handleUpdatePipelineStatus(
                          item.id,
                          e.target.value as 'saved' | 'applied' | 'interviewing' | 'offered' | 'rejected' | 'archived'
                        )
                      }
                      className="text-xs font-semibold px-2 py-0.5 rounded border border-neutral-300 bg-white text-neutral-800 cursor-pointer"
                    >
                      <option value="saved">Saved</option>
                      <option value="applied">Applied</option>
                      <option value="interviewing">Interviewing</option>
                      <option value="offered">Offered 🎉</option>
                      <option value="rejected">Rejected</option>
                      <option value="archived">Archived</option>
                    </select>
                  </div>
                </article>
              ))
            )}
          </div>
        )}

        {/* TAB 3: TELEMETRY */}
        {activeTab === 'telemetry' && (
          <div className="space-y-3">
            <div>
              <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider">
                LangGraph Workflow Telemetry
              </h3>
              <p className="text-[11px] text-neutral-500">Real-time Node Waterfall & Execution Durations</p>
            </div>

            {executions.length === 0 ? (
              <div className="p-8 text-center text-neutral-400 text-xs border border-dashed rounded-xl border-neutral-300">
                No workflow telemetry recorded yet.
              </div>
            ) : (
              executions.map((exec) => (
                <div
                  key={exec.execution_id}
                  className="p-3 bg-neutral-50 border border-neutral-200 rounded-xl space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] font-semibold text-neutral-700">
                      {exec.execution_id}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        exec.status === 'completed'
                          ? 'bg-emerald-100 text-emerald-800'
                          : exec.status === 'failed'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {exec.status}
                    </span>
                  </div>

                  {exec.task && <p className="text-neutral-700 font-medium">Task: {exec.task}</p>}

                  {exec.events && exec.events.length > 0 && (
                    <div className="space-y-1.5 pt-1">
                      <p className="text-[11px] text-neutral-400 font-semibold uppercase">Node Execution Sequence</p>
                      {exec.events.map((evt, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between text-[11px] bg-white p-1.5 rounded border border-neutral-200/60"
                        >
                          <div className="flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            <span className="font-medium text-neutral-800">{evt.node_name}</span>
                          </div>
                          <div className="flex items-center gap-2 text-neutral-500 font-mono">
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

        {/* TAB 4: NOTIFICATIONS & CONFIRMATION */}
        {activeTab === 'notifications' && (
          <div className="space-y-3">
            <div>
              <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider">
                Notifications & Confirmations
              </h3>
              <p className="text-[11px] text-neutral-500">Human-in-the-Loop Decisions & Reminders</p>
            </div>

            {notifications.length === 0 ? (
              <div className="p-8 text-center text-neutral-400 text-xs border border-dashed rounded-xl border-neutral-300">
                All caught up! Zero pending notifications or confirmation requests.
              </div>
            ) : (
              notifications.map((notif) => (
                <div
                  key={notif.id}
                  className={`p-3.5 rounded-xl border space-y-2 text-xs ${
                    notif.requires_confirmation
                      ? 'bg-amber-50/80 border-amber-300'
                      : 'bg-neutral-50 border-neutral-200'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 font-bold text-neutral-900">
                      {notif.requires_confirmation ? (
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      ) : (
                        <Bell className="w-3.5 h-3.5 text-blue-600" />
                      )}
                      <span>{notif.title}</span>
                    </div>
                    <span className="text-[10px] uppercase font-semibold text-neutral-400">
                      {notif.priority}
                    </span>
                  </div>

                  <p className="text-neutral-700 leading-relaxed">{notif.message}</p>

                  {notif.requires_confirmation && notif.confirmation_token && (
                    <div className="pt-2 border-t border-amber-200 flex items-center justify-between">
                      <span className="text-[11px] text-amber-800 font-medium flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3 text-amber-700" />
                        Requires User Confirmation
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
      </div>
    </aside>
  );
};
