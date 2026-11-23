import type { UpgradeView } from "@/lib/upgrade";
import { CheckAgain } from "./CheckAgain";

export function SubscribeView({ view }: { view: Extract<UpgradeView, { kind: "subscribe" }> }) {
  return (
    <>
      <h1>Get full access.</h1>
      {view.offer ? (
        <div className="promotion-offer">
          <p>
            <strong>{view.offer.badge}</strong>
          </p>
          <h2>{view.offer.headline}</h2>
          <p>{view.offer.body}</p>
          {view.offer.ends ? <p>Offer ends {view.offer.ends}.</p> : null}
        </div>
      ) : null}
      {view.url ? (
        <p>
          <a aria-describedby="new-tab-note" className="button button-primary" href={view.url} rel="noreferrer" target="_blank">
            Subscribe on Substack
          </a>{" "}
          <span id="new-tab-note">Opens in a new tab.</span>
        </p>
      ) : (
        <p>Subscribe from the newsletter&apos;s page on Substack.</p>
      )}
      <p>Subscriptions are sold and billed by Substack. When you have subscribed, come back and press Check again.</p>
      <CheckAgain />
    </>
  );
}
