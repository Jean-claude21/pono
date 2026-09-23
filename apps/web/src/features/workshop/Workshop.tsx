import { Link } from "@tanstack/react-router";
import type { Environment, ProjectState, ProjectSummary, Workshop as WorkshopData } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { dateTime, integer, relativeTime } from "@/lib/format";
import {
  STATES,
  countLabel,
  deploymentStatusLabel,
  environmentLabel,
  filterLabel,
  hostOf,
  stateLabel,
  verdictText,
  verdictTone,
} from "./labels";
import { QuotaMeter } from "./QuotaMeter";

type Props = {
  workshop: WorkshopData;
  filter: ProjectState | undefined;
};

/** The workshop (US2): what needs a decision first, then every project in rows (FR-026, FR-027). */
export function Workshop({ workshop, filter }: Props) {
  const total = STATES.reduce((sum, state) => sum + (workshop.counts[state] ?? 0), 0);
  return (
    <>
      <div className="topline">
        <div>
          <h1>{m.workshop_title()}</h1>
          <div className="counts mute">
            {STATES.map((state) => (
              <span key={state}>
                <b style={(workshop.counts[state] ?? 0) > 0 ? toneOf(state) : undefined}>
                  {integer(workshop.counts[state] ?? 0)}
                </b>
                {countLabel(state)}
              </span>
            ))}
          </div>
        </div>
        <Link className="btn btn-ghost btn-sm" to="/workshop/import">
          {m.workshop_import()}
        </Link>
      </div>

      <Verdicts workshop={workshop} />

      {total === 0 ? (
        <Empty />
      ) : (
        <>
          <div className="filters" role="group" aria-label={m.filter_group_label()}>
            <FilterTab label={m.filter_all()} count={total} pressed={filter === undefined} />
            {STATES.map((state) => (
              <FilterTab
                key={state}
                state={state}
                label={filterLabel(state)}
                count={workshop.counts[state] ?? 0}
                pressed={filter === state}
              />
            ))}
          </div>
          <ProjectTable projects={workshop.projects} />
        </>
      )}
    </>
  );
}

function toneOf(state: ProjectState): { color?: string } {
  if (state === "warning") return { color: "var(--warning)" };
  if (state === "failing") return { color: "var(--failing)" };
  return {};
}

function FilterTab({
  state,
  label,
  count,
  pressed,
}: {
  state?: ProjectState;
  label: string;
  count: number;
  pressed: boolean;
}) {
  return (
    <Link
      to="/workshop"
      search={state ? { state } : {}}
      role="button"
      aria-pressed={pressed}
      className="filter-tab"
    >
      {label}
      <span className="figures">{integer(count)}</span>
    </Link>
  );
}

function Verdicts({ workshop }: { workshop: WorkshopData }) {
  const [first, ...rest] = workshop.verdicts;
  if (!first) return null;
  const project = workshop.projects.find((item) => item.id === first.projectId);
  const name = project?.name ?? "";
  const { title, body } = verdictText(first.code, name);
  return (
    <div className={verdictTone(first.code) === "healthy" ? "verdict healthy" : "verdict"}>
      <div>
        <span className="mono-label">{m.verdict_label({ name })}</span>
        <h3>{title}</h3>
        <p>{body}</p>
        {rest.length > 0 ? (
          <p className="mono-label" style={{ marginTop: 10 }}>
            {m.verdict_more({ count: integer(rest.length) })}
          </p>
        ) : null}
      </div>
      <Link
        className="btn btn-ghost btn-sm"
        style={{ flexShrink: 0 }}
        to="/workshop/projects/$projectId"
        params={{ projectId: first.projectId }}
      >
        {m.verdict_open()}
      </Link>
    </div>
  );
}

function Empty() {
  return (
    <div className="verdict healthy">
      <div>
        <h3>{m.empty_title()}</h3>
        <p>{m.empty_body()}</p>
      </div>
      <Link className="btn btn-primary btn-sm" style={{ flexShrink: 0 }} to="/workshop/connections">
        {m.empty_cta()}
      </Link>
    </div>
  );
}

function ProjectTable({ projects }: { projects: ProjectSummary[] }) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th>{m.table_project()}</th>
          <th>{m.table_state()}</th>
          <th>{m.table_environments()}</th>
          <th>{m.table_last_deployment()}</th>
          <th className="num">{m.table_quota()}</th>
        </tr>
      </thead>
      <tbody>
        {projects.map((project) => (
          <ProjectRow key={project.id} project={project} />
        ))}
      </tbody>
    </table>
  );
}

function ProjectRow({ project }: { project: ProjectSummary }) {
  const production = project.environments.find((environment) => environment.kind === "production");
  const deployment = project.lastDeployment;
  return (
    <tr>
      <td className="project">
        <Link
          to="/workshop/projects/$projectId"
          params={{ projectId: project.id }}
          style={{ textDecoration: "none" }}
        >
          {project.name}
        </Link>
        <small>{hostOf(production?.url) || project.repository}</small>
      </td>
      <td>
        <span className={`state state-${project.state}`}>{stateLabel(project.state)}</span>
        {project.stale ? (
          <small className="mono-label" style={{ display: "block", marginTop: 4, color: "var(--warning)" }}>
            {m.stale_label()}
          </small>
        ) : null}
      </td>
      <td>
        <Environments environments={project.environments} />
      </td>
      <td>
        {deployment ? (
          <span title={dateTime(deployment.startedAt)}>
            {deployment.status === "succeeded"
              ? relativeTime(deployment.startedAt)
              : `${deploymentStatusLabel(deployment.status)} · ${relativeTime(deployment.startedAt)}`}
            {deployment.author ? <span className="mute"> · {deployment.author}</span> : null}
          </span>
        ) : (
          <span className="mute">{m.deployment_none()}</span>
        )}
      </td>
      <td className="num">
        {project.quota ? (
          <QuotaMeter quota={project.quota} />
        ) : (
          <span className="mute" style={{ fontSize: 13 }}>
            {m.quota_not_tracked()}
          </span>
        )}
      </td>
    </tr>
  );
}

const KINDS: Environment["kind"][] = ["production", "preview", "development"];

/** prod · preview · dev: lit when the address answers, red when it does not, dim when absent. */
function Environments({ environments }: { environments: Environment[] }) {
  return (
    <span className="env">
      {KINDS.map((kind) => {
        const present = environments.filter((environment) => environment.kind === kind);
        const down = present.some((environment) => environment.linkStatus === "down");
        const up = present.some((environment) => environment.linkStatus === "up");
        const className = down ? "down" : up ? "on" : undefined;
        const first = present[0];
        return first?.url ? (
          <a key={kind} className={className} href={first.url} target="_blank" rel="noreferrer">
            {environmentLabel(kind)}
          </a>
        ) : (
          <span key={kind} className={className}>
            {environmentLabel(kind)}
          </span>
        );
      })}
    </span>
  );
}
