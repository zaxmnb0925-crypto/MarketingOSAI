import Link from "next/link";

export default function Home() {
  return (
    <main className="public-site">
      <header className="public-nav">
        <Link className="public-brand" href="/">
          <span className="brand-mark small">M</span>
          <strong>MarketingOS</strong>
        </Link>

        <nav className="public-nav-links">
          <a href="#features">功能</a>
          <a href="#plans">方案</a>
          <Link href="/login">登入</Link>
          <Link className="public-nav-cta" href="/register">免費開始</Link>
        </nav>
      </header>

      <section className="public-hero">
        <div>
          <div className="eyebrow">MARKETINGOS AI</div>
          <h1>讓品牌內容，<br />更快開始。</h1>
          <p>
            集中管理品牌資料，使用 AI 建立社群內容，
            讓品牌溝通更一致、更有效率。
          </p>

          <div className="public-hero-actions">
            <Link className="dashboard-action" href="/register">
              免費建立工作空間
            </Link>
            <Link className="dashboard-secondary-action" href="/login">
              登入工作空間
            </Link>
          </div>
        </div>

        <div className="public-hero-card">
          <div className="eyebrow">BRAND WORKSPACE</div>
          <h2>從品牌開始，建立一致內容。</h2>
          <div className="public-lines"><span /><span /><span /></div>
          <div className="public-card-tags">
            <span>Brand Brain</span>
            <span>AI Content</span>
            <span>Quality</span>
          </div>
        </div>
      </section>

      <section className="public-section" id="features">
        <div className="eyebrow">WORKFLOW</div>
        <h2>一個工作空間，完成品牌內容流程。</h2>

        <div className="public-feature-grid">
          <article className="public-feature-card">
            <span>01</span>
            <h3>品牌管理</h3>
            <p>集中保存品牌定位、語氣與內容規範。</p>
          </article>
          <article className="public-feature-card">
            <span>02</span>
            <h3>AI 創作</h3>
            <p>依照品牌資料快速建立社群內容。</p>
          </article>
          <article className="public-feature-card">
            <span>03</span>
            <h3>品質治理</h3>
            <p>發布前檢視內容品質與品牌規則。</p>
          </article>
        </div>
      </section>

      <section className="public-section public-plans" id="plans">
        <div>
          <div className="eyebrow">PLANS</div>
          <h2>從免費方案開始。</h2>
          <p>先建立工作空間，再依需求升級方案。</p>
        </div>

        <div className="public-price-grid">
          <div className="public-price-card">
            <strong>Free</strong>
            <span>NT$ 0 / 月</span>
          </div>
          <div className="public-price-card featured">
            <strong>Pro</strong>
            <span><del>NT$ 1,399</del> 優惠價 NT$ 990 / 月</span>
          </div>
          <div className="public-price-card">
            <strong>Business</strong>
            <span>NT$ 3,990 / 月</span>
          </div>
        </div>
      </section>

      <footer className="public-footer">
        <span>© MarketingOS</span>
        <div><Link href="/login">登入</Link><Link href="/register">註冊</Link></div>
      </footer>
    </main>
  );
}
