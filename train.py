"""학습 모듈."""
import torch
import torch.nn.functional as F
from torch.autograd import Variable

import utils
import model

BATCH_SIZE = 128
LEARNING_RATE = 0.001
GAMMA = 0.99
TAU = 0.001


class Trainer:
    """트레이너."""

    def __init__(self, state_dim, action_dim, action_lim, ram):
        """초기화.

        :param state_dim: Dimensions of state (int)
        :param action_dim: Dimension of action (int)
        :param action_lim: Used to limit action in [-action_lim,action_lim]
        :param ram: replay memory buffer object
        :return:
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.action_lim = action_lim
        self.ram = ram
        self.iter = 0
        self.noise = utils.OrnsteinUhlenbeckActionNoise(self.action_dim)

        self.actor = model.Actor(self.state_dim, self.action_dim,
                                 self.action_lim)
        self.target_actor = model.Actor(self.state_dim, self.action_dim,
                                        self.action_lim)
        self.actor_optimizer = torch.optim.Adam(self.actor.parameters(),
                                                LEARNING_RATE)

        self.critic = model.Critic(self.state_dim, self.action_dim)
        self.target_critic = model.Critic(self.state_dim, self.action_dim)
        self.critic_optimizer = torch.optim.Adam(self.critic.parameters(),
                                                 LEARNING_RATE)

        utils.hard_update(self.target_actor, self.actor)
        utils.hard_update(self.target_critic, self.critic)

    def get_exploitation_action(self, state):
        """활용을 위한 동작 얻기.

        gets the action from target actor added with exploration noise

        :param state: state (Numpy array)
        :return: sampled action (Numpy array)
        """
        state = Variable(torch.from_numpy(state))
        action = self.target_actor.forward(state).detach()
        return action.data.numpy()

    def get_exploration_action(self, state):
        """탐험을 위한 동작 얻기.

        gets the action from actor added with exploration noise

        :param state: state (Numpy array)
        :return: sampled action (Numpy array)
        """
        state = Variable(torch.from_numpy(state))
        action = self.actor.forward(state).detach()
        new_action = action.data.numpy() + (self.noise.sample() *
                                            self.action_lim)
        return new_action

    def optimize(self):
        """최적화.

        Samples a random batch from replay memory and performs optimization

        :return:
        """
        s1, a1, r1, s2 = self.ram.sample(BATCH_SIZE)

        s1 = Variable(torch.from_numpy(s1))
        a1 = Variable(torch.from_numpy(a1))
        r1 = Variable(torch.from_numpy(r1))
        s2 = Variable(torch.from_numpy(s2))

        # ---------------------- optimize critic ----------------------
        # Use target actor exploitation policy here for loss evaluation
        a2 = self.target_actor.forward(s2).detach()
        next_val = torch.squeeze(self.target_critic.forward(s2, a2).detach())
        # y_exp = r + gamma*Q'( s2, pi'(s2))
        y_expected = r1 + GAMMA * next_val
        # y_pred = Q( s1, a1)
        y_predicted = torch.squeeze(self.critic.forward(s1, a1))
        # compute critic loss, and update the critic
        loss_critic = F.smooth_l1_loss(y_predicted, y_expected)
        self.critic_optimizer.zero_grad()
        loss_critic.backward()
        self.critic_optimizer.step()

        # ---------------------- optimize actor ----------------------
        pred_a1 = self.actor.forward(s1)
        loss_actor = -1 * torch.sum(self.critic.forward(s1, pred_a1))
        self.actor_optimizer.zero_grad()
        loss_actor.backward()
        self.actor_optimizer.step()

        utils.soft_update(self.target_actor, self.actor, TAU)
        utils.soft_update(self.target_critic, self.critic, TAU)

    def save_models(self, episode_count):
        """모델 저장.

        saves the target actor and critic models

        :param episode_count: the count of episodes iterated
        :return:
        """
        torch.save(self.target_actor.state_dict(), './Models/' +
                   str(episode_count) + '_actor.pt')
        torch.save(self.target_critic.state_dict(), './Models/' +
                   str(episode_count) + '_critic.pt')
        print('Models saved successfully')

    def load_models(self, episode):
        """모델 읽기.

        loads the target actor and critic models, and copies them onto actor
            and critic models
        :param episode: the count of episodes iterated (used to find the file
            name)
        :return:
        """
        self.actor.load_state_dict(torch.load('./Models/' + str(episode) +
                                              '_actor.pt'))
        self.critic.load_state_dict(torch.load('./Models/' + str(episode) +
                                               '_critic.pt'))
        utils.hard_update(self.target_actor, self.actor)
        utils.hard_update(self.target_critic, self.critic)
        print('Models loaded succesfully')
