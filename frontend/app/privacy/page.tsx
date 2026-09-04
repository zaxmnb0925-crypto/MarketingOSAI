export const metadata = {
  title: "Privacy Policy | MarketingOS AI",
  description: "Closed Beta privacy notice for MarketingOS AI.",
};

const sections = [
  {
    title: "1. Service identity",
    body: [
      "MarketingOS AI is the service name used for this Closed Beta.",
      "This notice describes how the service handles information during the Closed Beta. It does not invent or assert a legal entity name, postal address, or other operator information that has not yet been formally published.",
    ],
  },
  {
    title: "2. Information we collect",
    body: [
      "We may process account and authentication information, workspace and brand information, content and prompts you submit, generated content, usage records, publication records, connected social-account information, audit records, and technical information required to operate and secure the service.",
      "We may also process identifiers and authorization information provided through integrations that you choose to connect.",
    ],
  },
  {
    title: "3. Why we process information",
    body: [
      "We use information to authenticate users, provide workspace features, generate and manage content, operate publication workflows, measure usage, enforce plan or credit limits, secure the service, investigate failures, and improve reliability.",
    ],
  },
  {
    title: "4. AI and service providers",
    body: [
      "Content-generation requests may be processed by configured third-party AI or infrastructure providers where required to provide the requested feature.",
      "We limit the information sent to a provider to information required for the relevant service function and our configured integration.",
    ],
  },
  {
    title: "5. Meta and Facebook integrations",
    body: [
      "If you choose to connect a Meta or Facebook account or Page, the service may process identifiers, permissions, authorization information, Page information, publication state, and related records required to provide the integration.",
      "Connecting a social account is optional. Publication operations remain subject to the service's authorization and safety controls.",
    ],
  },
  {
    title: "6. Cookies and session data",
    body: [
      "The service uses session and authentication mechanisms needed to keep users signed in and to protect authenticated requests.",
      "Security-related cookie and session settings are used as part of the application's authentication boundary.",
    ],
  },
  {
    title: "7. Usage, credit, and billing-related data",
    body: [
      "The service may record feature usage, AI usage, token or processing usage, credit consumption, and related operational records to enforce service limits, operate billing controls, prevent abuse, and maintain internal accounting. Customer-facing pages do not expose token, cost, credit-balance, or internal accounting telemetry.",
    ],
  },
  {
    title: "8. Data retention",
    body: [
      "Information is retained only for as long as reasonably necessary for the service purpose, security, audit, dispute handling, or applicable legal obligations.",
      "A fixed retention duration is not stated in this Closed Beta notice because no repository-supported fixed duration has been established for all data categories.",
    ],
  },
  {
    title: "9. Security",
    body: [
      "We use application and operational safeguards designed to protect authentication, workspace isolation, credentials, publication workflows, and service data.",
      "No online service can guarantee absolute security. Closed Beta participants should not submit information that is unnecessary for testing the service.",
    ],
  },
  {
    title: "10. Your choices and rights",
    body: [
      "You may choose whether to connect optional third-party integrations and may stop using the service at any time.",
      "Requests concerning access, correction, deletion, or other applicable data rights can be raised through the support channel provided with the service or Closed Beta invitation.",
    ],
  },
  {
    title: "11. Account and data deletion",
    body: [
      "Where an account-deletion or data-deletion flow is available, you may use that flow. You may also request deletion through the support channel provided with your account or Closed Beta invitation.",
      "Deletion requests may be subject to information that must be retained temporarily for security, audit, dispute handling, or applicable legal obligations.",
    ],
  },
  {
    title: "12. Third-party services",
    body: [
      "Optional integrations and infrastructure providers may process information under their own terms and privacy practices.",
      "You should review the privacy information of any third-party service you choose to connect.",
    ],
  },
  {
    title: "13. Changes to this notice",
    body: [
      "This notice may be updated as the Closed Beta evolves, new integrations are introduced, or the service prepares for broader public availability.",
      "Material changes should be reflected on this page before they take effect for broader public use.",
    ],
  },
  {
    title: "14. Contact",
    body: [
      "Closed Beta participants should use the support or contact channel provided with their account, service interface, or Beta invitation.",
      "Additional formally published operator and contact information will be added before broader public release where required.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <main className="mx-auto min-h-screen w-full max-w-4xl px-6 py-12">
      <div className="space-y-3">
        <p className="text-sm font-medium uppercase tracking-wide text-neutral-500">
          Closed Beta
        </p>

        <h1 className="text-3xl font-semibold tracking-tight">
          Privacy Policy
        </h1>

        <p className="max-w-3xl text-sm leading-6 text-neutral-600">
          This privacy notice applies to the MarketingOS AI Closed Beta and
          describes the principal categories of information handled by the
          service.
        </p>
      </div>

      <div className="mt-10 space-y-10">
        {sections.map((section) => (
          <section key={section.title} className="space-y-3">
            <h2 className="text-xl font-semibold">
              {section.title}
            </h2>

            {section.body.map((paragraph) => (
              <p
                key={paragraph}
                className="text-sm leading-7 text-neutral-700"
              >
                {paragraph}
              </p>
            ))}
          </section>
        ))}
      </div>

      <div className="mt-12 border-t pt-6 text-sm">
        <a
          href="/"
          className="underline underline-offset-4"
        >
          Back to MarketingOS AI
        </a>
      </div>
    </main>
  );
}
