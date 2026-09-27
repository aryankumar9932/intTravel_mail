# 📖 Overview
This project explores **the unification of multiple recommendation tasks within a single, end-to-end generative model**.

## FastAPI integration

FastAPI is the single entry point for the complete project: it serves the existing
web interface at `/`, the API at `/api/*`, the OpenAPI documentation, and the
IntTravel recommendation engine. From the `travel-guard` directory, install the
dependencies and start it:

The trip planner shows local hotel picks when available and provides a live
Google Maps hotel search for any destination entered.

```bash
pip install -r requirements.txt
python -m uvicorn fastapi_app:app --host 0.0.0.0 --port 8000
```

On Windows, double-click [run_fastapi.bat](./run_fastapi.bat), or run
[run_project.bat](./run_project.bat) if you also want to rebuild the processed
data before startup. Do not run `trip_planner_app.py` separately; FastAPI
imports its project logic.

### Share a public API URL

The API is not publicly reachable while it runs on `127.0.0.1`; that address is
only your computer. To share it, push this repository to GitHub and deploy it
with Render:

1. In Render, choose **New > Blueprint** and select the repository.
2. Render reads [render.yaml](./render.yaml), builds the data, and starts FastAPI.
3. Share the generated URL, for example `https://inttravel.onrender.com`.

The other project then uses:

```javascript
const API_URL = "https://inttravel.onrender.com";
fetch(`${API_URL}/api/plan`, {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({
    destination: "Jaipur",
    days: 3,
    travelerType: "solo"
  })
});
```

Set `CORS_ORIGINS` in Render to the exact frontend origin, for example
`https://my-frontend.example.com`. The included [Dockerfile](./Dockerfile)
can also deploy the same API to any Docker-compatible host.

The interactive API documentation is available at
`http://localhost:8000/docs`; OpenAPI JSON is available at
`http://localhost:8000/openapi.json`.

| Method | Endpoint | Purpose |
|:---|:---|:---|
| GET | `/health` | Service health check |
| POST | `/api/plan` | Build a safety-aware itinerary |
| POST | `/api/disruptions` | Add a live alert and recalculate the itinerary |
| GET | `/api/recommendations` | Get ML-ranked POI recommendations |
| POST | `/api/book-guide` | Create a guide booking |
| GET | `/api/datasets` | Read the safety, hotel, and guide datasets |
| GET | `/api/data-overview` | Check the ML input data status |
| GET | `/api/ml-status` | Read recommender metadata |

Example request:

```bash
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d "{\"destination\":\"Jaipur\",\"days\":3,\"travelerType\":\"solo\"}"
```

By default, browser requests from any origin are accepted for integration
development. Set `CORS_ORIGINS` to a comma-separated allowlist in production,
for example `https://my-frontend.example.com`.

*   **IntTravel**: Our foundational work that introduced a large-scale, real-world dataset and a generative framework for integrated multi-task travel recommendation.
*   **IntHQ**: The advanced successor to IntTravel, which identifies and resolves the "threefold collapse" in generative multi-task models with a novel architecture.


# IntTravel: A Large-Scale Real-World Dataset  [![Data Set](https://img.shields.io/badge/Data-Set-green)](https://huggingface.co/datasets/GD-ML/IntTravel_dataset/tree/main)

We introduce **IntTravel**, the first large-scale public dataset for **integrated travel recommendation**, including **4.1 billion interactions from 163 million users with 7.3 million POIs**. Built upon this dataset, we introduce an end-to-end, **decoder-only generative framework for multi-task recommendation**. 

All data are collected from a leading provider of digital map, navigation and real-time traffic information in China. Here is a simple dataset in `data_process/raw_data` and a more comprehensive dataset in [Hugging Face](https://huggingface.co/datasets/GD-ML/IntTravel_dataset/tree/main). The code in `data_process` demonstrates how to construct the input sequence of the model and the labels for all tasks based on the original data.

### Information of POIs

The IntTravel dataset contains **7,291,872** POIs (Point of Interests) distributed across several major cities in China. Each POI is described by the following fields:

| Field | Description |
|:---|:---|
| POI ID | A unique identifier for each Point of Interest. |
| Normalized score | A 0-1 score reflecting the overall popularity of the POI. |
| Geographic ID | Identifier for the POI's geographic block. Same GIDs indicate geographical proximity. |
| Category ID | A numerical identifier for the Point of Interest's category. |
| Administrative Region ID | The identifier for the administrative region of the POI. |
| Coordinates | The spatial coordinates of the POI on a 2D plane. |

### User Profiles
The IntTravel dataset contains **162,815,861** users, each described by the following fields:

| Field | Description |
|:---|:---|
| User ID | A unique identifier assigned to each user. |
| Profile Feature 1 | The first profile feature. |
| ... | ... |
| Profile Feature 6 | The sixth profile feature. |


### User Interactions
The IntTravel dataset includes **4,129,827,011** user interaction events. Each event is characterized by the following fields:

| Field | Description |
|:---|:---|
| User ID | A unique identifier for the user who performed the interaction. |
| Timestamp | The time of the user interaction, recorded in milliseconds. |
| Action Type | A numerical ID representing the type of user behavior (e.g., click). |
| POI ID | The identifier of the Point of Interest involved in the interaction. |
| Geographic ID | The geographic block ID where the user was during the interaction. |
| Administrative Region ID | The administrative region ID where the user was during the interaction. |
| Weather | A numerical ID representing the weather condition during the interaction. |
| Travel Mode | A numerical ID for the user's chosen travel mode. |
| Via POI ID | The identifier for a way-point POI added by the user. |

# IntTravel: Generative Framework for Integrated Multi-Task Travel Recommendation  [![Paper Page](https://img.shields.io/badge/Paper-Page-blue)](https://arxiv.org/abs/2602.11664)

IntTravel incorporates information preservation, selection, and factorization to balance task collaboration with specialized differentiation, yielding substantial performance gains. IntTravel has been successfully deployed on Amap serving hundreds of millions of users.

<img width="5275" height="2122" alt="IntTravel_multi_task_framework" src="https://github.com/user-attachments/assets/5ddf5382-299f-41ed-aeac-2b475883cb7a" />

IntTravel is **the first multi-task solution for generative recommendation**. We propose a bottom-up multi-task method to handle multiple tasks within a single generative model. The approach comprises three modules:

*   **Task-Guided Information Persistence (TIP)** ensures maximum propagation of task-relevant information in the decoder.
*   **Task-Specific Selective Gating (TSG)** enables each task to filter useful information from the decoder's output.
*   **Task-Aware Scenario Factorization (TSF)** empowers each task to factorize its output based on specific scenarios.




# IntHQ: Task-Interactive Hierarchical Query on Dual-Stream Representations for Generative Recommendation  [![Paper Page](https://img.shields.io/badge/Paper-Page-blue)](https://arxiv.org/abs/2608.09634)

</div>

Multi-task learning over heterogeneous data is fundamental to modern recommendation, while generative models are emerging as the backbone of next-generation recommenders. However, the integration of multi-task learning into the generative paradigm remains largely unexplored. Existing multi-task recommenders, in both discriminative and generative paradigms, extract task-relevant features from a single task-agnostic representation and wire tasks into a predefined conversion funnel. We show that this scheme is inherently prone to a threefold collapse. 
*   **Source collapse**, where task-specific signals are injected late and diluted in the shared latent space. 
*   **Relational collapse**, where task dependencies are either implicitly absorbed by the backbone or statically fixed by predefined funnels. 
*   **Hierarchical collapse**, where tasks depend on features at different scales and shift across training stages.

<img width="3675" height="2135" alt="image" src="https://github.com/user-attachments/assets/c6ed3df6-34ea-4dcc-b3c2-c3bde0596c65" />

**IntHQ** is a multi-task generative recommender with three components, each alleviating one collapse:

* **Dual-Stream Decoupling (DSD)** injects task identity into the computation stream early and separates the shared context stream from the task-specific stream, alleviating signal dilution.

* **Task-Interactive Modeling (TIM)** replaces the predefined funnel with explicit cross-task interaction, letting each task condition on the realized outcomes of its predecessors with learned, input-adaptive strength.

* **Hierarchical Querying (HQ)** lets each task gather multi-scale information across different layers at different training stages.

In offline evaluations, **IntHQ** consistently outperforms competitive encoder backbones under four representative task-head configurations. Deployed in production on Amap, serving hundreds of millions of users for travel recommendation, **IntHQ** yields a 1.60% relative UVCTR lift.


# 📚 Citation

If you find our papers and code helpful for your research, please consider starring our repository ⭐ and citing our work ✏️.

```bibtex
@article{yan2026inttravel,
  title={IntTravel: A Real-World Dataset and Generative Framework for Integrated Multi-Task Travel Recommendation},
  author={Yan, Huimin and Xu, Longfei and Sun, Junjie and Liu, Zheng and Luo, Wei and Liu, Kaikui and Chu, Xiangxiang},
  journal={arXiv preprint arXiv:2602.11664},
  year={2026}
}
@article{sun2026inthq,
  title={IntHQ: Task-Interactive Hierarchical Query on Dual-Stream Representations for Generative Recommendation},
  author={Sun, Junjie and Xu, Longfei and Yan, Huimin and Luo, Wei and Liu, Kaikui and Chu, Xiangxiang},
  journal={arXiv preprint arXiv:2608.09634},
  year={2026}
}
```
