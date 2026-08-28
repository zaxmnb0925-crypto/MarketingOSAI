export default function Home() {
  return (
    <main className="marketing-page">
      <nav className="public-nav" aria-label="主要導覽">
        <a className="public-brand" href="/">
          <span className="brand-mark small">M</span>
          <strong>MarketingOS AI</strong>
        </a>
        <div className="public-nav-links">
          <a href="#capabilities">產品能力</a>
          <a href="#roadmap">產品藍圖</a>
          <a href="/pricing">方案價格</a>
          <a href="/login">登入</a>
          <a className="public-nav-cta" href="/register">免費開始</a>
        </div>
      </nav>

      <section className="hero-section">
        <div className="hero-copy">
          <div className="public-kicker">為所有中文市場商家打造</div>
          <h1>讓品牌策略、AI 內容與社群發布，形成一套可持續的行銷工作流。</h1>
          <p>
            MarketingOS AI 協助商家整理品牌脈絡、產生內容並管理發布流程，
            讓每一次創作都建立在一致的品牌方向上。
          </p>
          <div className="hero-actions">
            <a className="public-primary" href="/register">免費建立 Workspace</a>
            <a className="public-secondary" href="/pricing">查看公開價格</a>
          </div>
          <div className="hero-trust">
            <span>免費方案可直接註冊</span>
            <span>HttpOnly 安全工作階段</span>
            <span>客戶端不顯示內部 AI 成本</span>
          </div>
        </div>

        <div className="hero-console" aria-label="MarketingOS 工作流程預覽">
          <div className="hero-console-top"><span /><span /><span /></div>
          <div className="hero-console-label">BRAND WORKFLOW</div>
          <h2>從品牌脈絡到內容發布</h2>
          <ol>
            <li><span>01</span><div><strong>建立品牌資料</strong><small>整理語氣、受眾與定位</small></div></li>
            <li><span>02</span><div><strong>AI 協作生成</strong><small>依品牌方向建立內容草稿</small></div></li>
            <li><span>03</span><div><strong>審核與發布</strong><small>透過受控流程連接 Meta／Facebook</small></div></li>
          </ol>
        </div>
      </section>

      <section className="public-section" id="capabilities">
        <div className="section-heading">
          <div className="public-kicker">AVAILABLE NOW</div>
          <h2>目前已具備的產品基礎</h2>
          <p>只呈現已存在於系統並通過測試的能力。</p>
        </div>
        <div className="capability-grid">
          <article><span>01</span><h3>品牌脈絡管理</h3><p>集中整理品牌定位、受眾、語氣與內容方向，減少每次重新說明。</p></article>
          <article><span>02</span><h3>AI 內容工作流</h3><p>依 Workspace 與品牌資料產生、保存及追蹤內容草稿。</p></article>
          <article><span>03</span><h3>Meta／Facebook 流程</h3><p>具備 OAuth、權限檢查、審核與受控發布基礎；不宣稱尚未接入的平台。</p></article>
          <article><span>04</span><h3>團隊與方案邊界</h3><p>Workspace 角色、訂閱與權限分離，內部成本與用量不暴露給客戶。</p></article>
        </div>
      </section>

      <section className="roadmap-section" id="roadmap">
        <div className="roadmap-copy">
          <div className="public-kicker">PRODUCT ROADMAP</div>
          <h2>正在打造的差異化智慧層</h2>
          <p>
            以下是產品方向，尚未作為目前可用功能銷售。每項能力都會先完成
            資料授權、租戶隔離與可驗證測試，再正式開放。
          </p>
        </div>
        <div className="roadmap-list">
          <article><span>規劃中</span><div><h3>更多廣告與社群平台</h3><p>逐步擴充平台連接，但維持各平台獨立授權與可撤銷權限。</p></div></article>
          <article><span>規劃中</span><div><h3>即時關鍵字與趨勢訊號</h3><p>串接可信資料來源，標示更新時間與來源，不以 AI 猜測冒充即時趨勢。</p></div></article>
          <article><span>研究中</span><div><h3>隱私安全的群體智慧</h3><p>僅使用取得授權、去識別與聚合後的模式改善回答，絕不讓其他商家的私有資料跨 Workspace 洩漏。</p></div></article>
        </div>
      </section>

      <section className="public-cta-section">
        <div><div className="public-kicker">START FREE</div><h2>先建立你的品牌 Workspace</h2><p>任何人都能自行註冊，從免費方案開始。</p></div>
        <div className="hero-actions"><a className="public-primary" href="/register">免費建立帳號</a><a className="public-secondary" href="/pricing">比較方案</a></div>
      </section>
    </main>
  );
}
