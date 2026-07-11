import torch
import torch.nn as nn


class RSSMTrajectoryPredictor(nn.Module):
    def __init__(
        self,
        state_dim=10,
        action_dim=3,
        hidden_dim=384,
        action_hidden_dim=None,
        stochastic_dim=None,
        pred_len=5,
    ):
        super(RSSMTrajectoryPredictor, self).__init__()
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.hidden_dim = hidden_dim
        self.action_hidden_dim = action_hidden_dim or hidden_dim // 2
        self.stochastic_dim = stochastic_dim or hidden_dim // 2
        self.pred_len = pred_len

        self.state_encoder = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ELU(),
        )
        self.action_encoder = nn.Sequential(
            nn.Linear(action_dim, self.action_hidden_dim),
            nn.ELU(),
        )
        self.rnn = nn.GRUCell(
            input_size=self.stochastic_dim + self.action_hidden_dim,
            hidden_size=hidden_dim,
        )
        self.prior_net = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ELU(),
            nn.Linear(hidden_dim, self.stochastic_dim),
        )
        self.posterior_net = nn.Sequential(
            nn.Linear(hidden_dim + hidden_dim, hidden_dim),
            nn.ELU(),
            nn.Linear(hidden_dim, self.stochastic_dim),
        )
        self.state_decoder = nn.Sequential(
            nn.Linear(hidden_dim + self.stochastic_dim, hidden_dim),
            nn.ELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ELU(),
            nn.Linear(hidden_dim, state_dim),
        )

    def encode_context(self, obs_states, obs_actions):
        batch_size, obs_len, _ = obs_states.shape
        device = obs_states.device
        h_t = torch.zeros(batch_size, self.hidden_dim, device=device)
        z_t = torch.zeros(batch_size, self.stochastic_dim, device=device)
        zero_action = torch.zeros(batch_size, self.action_hidden_dim, device=device)
        encoded_obs_actions = self.action_encoder(obs_actions)

        for t in range(obs_len):
            prev_action = zero_action if t == 0 else encoded_obs_actions[:, t - 1]
            h_t = self.rnn(torch.cat([z_t, prev_action], dim=-1), h_t)
            encoded_state = self.state_encoder(obs_states[:, t])
            z_t = self.posterior_net(torch.cat([h_t, encoded_state], dim=-1))

        return h_t, z_t

    def rollout_from_context(self, h_t, z_t, future_actions):
        batch_size = future_actions.shape[0]
        if h_t.shape[0] == 1 and batch_size != 1:
            h_t = h_t.expand(batch_size, -1).contiguous()
            z_t = z_t.expand(batch_size, -1).contiguous()
        elif h_t.shape[0] != batch_size:
            raise ValueError("Context batch must be 1 or match future_actions batch.")

        encoded_future_actions = self.action_encoder(future_actions)
        pred_states = []
        for t in range(self.pred_len):
            h_t = self.rnn(torch.cat([z_t, encoded_future_actions[:, t]], dim=-1), h_t)
            z_t = self.prior_net(h_t)
            pred_state = self.state_decoder(torch.cat([h_t, z_t], dim=-1))
            pred_states.append(pred_state.unsqueeze(1))

        return torch.cat(pred_states, dim=1)

    def forward(self, obs_states, obs_actions, future_actions):
        h_t, z_t = self.encode_context(obs_states, obs_actions)
        return self.rollout_from_context(h_t, z_t, future_actions)
