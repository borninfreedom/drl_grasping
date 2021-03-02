from drl_grasping.envs.tasks.reach import Reach
from drl_grasping.perception import CameraSubscriber
from drl_grasping.perception import OctreeCreator
from gym_ignition.utils.typing import Observation
from gym_ignition.utils.typing import ObservationSpace
from typing import Tuple
import abc
import gym
import numpy as np


class ReachOctree(Reach, abc.ABC):

    # Overwrite parameters for ManipulationGazeboEnvRandomizer
    _camera_enable: bool = True
    _camera_type: str = 'rgbd_camera'
    _camera_position: Tuple[float, float, float] = (1.1, -0.75, 0.45)
    _camera_quat_xyzw: Tuple[float, float,
                             float, float] = (-0.0402991, -0.0166924, 0.9230002, 0.3823192)
    _camera_ros2_bridge_points: bool = True

    # TODO: replace with variable-sized replay buffer
    _octree_max_size = 25000

    def __init__(self,
                 agent_rate: float,
                 restrict_position_goal_to_workspace: bool = True,
                 shaped_reward: bool = True,
                 required_accuracy: float = 0.05,
                 octree_depth: int = 6,
                 octree_full_depth: int = 2,
                 octree_include_color: bool = False,
                 verbose: bool = False,
                 **kwargs):

        # Initialize the Task base class
        Reach.__init__(self,
                       agent_rate=agent_rate,
                       restrict_position_goal_to_workspace=restrict_position_goal_to_workspace,
                       shaped_reward=shaped_reward,
                       required_accuracy=required_accuracy,
                       verbose=verbose,
                       **kwargs)

        # Perception (RGB-D camera - point cloud)
        self.camera_sub = CameraSubscriber(topic=f'/{self._camera_type}/points',
                                           is_point_cloud=True,
                                           node_name=f'drl_grasping_point_cloud_sub_{self.id}')

        min_bound = (self._workspace_centre[0] - self._workspace_volume[0]/2,
                     self._workspace_centre[1] - self._workspace_volume[1]/2,
                     self._workspace_centre[2] - self._workspace_volume[2]/2)
        max_bound = (self._workspace_centre[0] + self._workspace_volume[0]/2,
                     self._workspace_centre[1] + self._workspace_volume[1]/2,
                     self._workspace_centre[2] + self._workspace_volume[2]/2)
        self.octree_creator = OctreeCreator(min_bound=min_bound,
                                            max_bound=max_bound,
                                            depth=octree_depth,
                                            full_depth=octree_full_depth,
                                            include_color=octree_include_color,
                                            use_sim_time=True,
                                            debug_draw=False,
                                            node_name=f'drl_grasping_octree_creator_{self.id}')

    def create_observation_space(self) -> ObservationSpace:

        # 0:n - octree
        # Note: octree is currently padded with zeros to have constant size
        # TODO: Customize replay buffer to support variable sized observations
        return gym.spaces.Box(low=0,
                              high=255,
                              shape=(self._octree_max_size,),
                              dtype=np.uint8)

    def get_observation(self) -> Observation:

        # Get the latest point cloud
        point_cloud = self.camera_sub.get_observation()

        # Contrust octree from this point cloud
        octree = self.octree_creator(point_cloud).numpy()

        # Pad octree with zeros to have a consistent length
        # TODO: Customize replay buffer to support variable sized observations
        if octree.shape[0] > self._octree_max_size:
            print(
                f"ERROR: Octree is larger than the maximum allowed size (exceeded with {octree.shape[0]})")
        octree = np.pad(octree,
                        (0, self._octree_max_size - octree.shape[0]),
                        'constant',
                        constant_values=0)

        # Create the observation
        observation = Observation(octree)

        if self._verbose:
            print(f"\nobservation: {observation}")

        # Return the observation
        return observation
